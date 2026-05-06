# Arak AI Chatbot v2.1

An intelligent assistant for the **Arak School Admin System** with **multi-layer AI fallback** and **per-request model control** from the dashboard.

## Architecture: Multi-Layer Fallback

```
┌─────────────────────────────────────────────────────────────┐
│                    Dashboard ChatWidget                      │
│              (settings panel → model_config)                 │
└────────────────────────┬────────────────────────────────────┘
                         │ POST /chat { message, model_config_data }
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Gemini 2.0 Flash Lite  (cloud, fastest, 30 rpm)   │
│           ↓ 429/quota error                                 │
│  Layer 2: Gemini 1.5 Flash       (cloud, 15 rpm)            │
│           ↓ 429/quota error                                 │
│  Layer 3: Ollama + Qwen 2.5 1.5B (local, offline)           │
│           ↓ all failed                                      │
│  Layer 4: sklearn TF-IDF + LogReg (builtin, always works)   │
└─────────────────────────────────────────────────────────────┘
```

**Rules:**
- Each layer can be enabled/disabled per-request from the dashboard
- Only falls to next layer on **429 / quota errors**
- Non-quota errors (auth, network) → raised immediately
- 60-second in-memory cache — same prompt skips all layers
- Console logs which layer was used: `[Chatbot] Using layer: X`

## Features

### Basic Queries
- Attendance, Grades, Schedules, Fees, Tasks, Events, Teachers, Classes

### Analytical Intents
- **Top Absentees** — "مين أكتر طلاب غياباً؟"
- **Weak Students** — "الطلاب الضعفاء في الرياضيات؟"
- **Class Summary** — "ملخص الفصل 1"
- **Unpaid Fees** — "كام طالب ما دفعوش؟"
- **Daily Summary** — "ملخص النهارده"

### RBAC

| Role | Access |
|------|--------|
| Super Admin / Admin | All intents |
| Teacher | Attendance, Grades, Schedule, Analytics, Tasks, Daily Summary |
| Parent | Attendance (own children), Grades, Fees, Schedule, Events |
| Student | Blocked |

## Project Structure

```text
arak-chatbot/
├── api/
│   ├── ai_service.py        # Multi-layer AI orchestrator (NEW)
│   ├── chat_router.py       # Chat endpoint + RBAC + intent handlers
│   ├── gemini_service.py    # Legacy single-model service (kept for reference)
│   ├── arak_client.py       # HTTP client for Arak Backend API
│   └── auth_middleware.py   # JWT authentication
├── pipeline/
│   ├── intent_classifier.py # sklearn TF-IDF + LogReg (Layer 4)
│   ├── embedder.py          # TF-IDF vectorizer
│   └── preprocessor.py      # Text normalization
├── models/                  # Pre-trained sklearn model files (.pkl)
├── data/
│   └── intents.json         # Training data
├── main.py
├── requirements.txt
├── .env.example
└── README.md
```

## Configuration

Copy `.env.example` to `.env` and fill in:

```env
ARAK_API_URL=http://localhost:5000/api
JWT_SECRET_KEY=your_jwt_secret
GEMINI_API_KEY=your_gemini_key

# Layer toggles (defaults if dashboard doesn't send config)
ENABLE_GEMINI_LITE=true
ENABLE_GEMINI_FLASH=true
ENABLE_OLLAMA=true
ENABLE_SKLEARN=true

# Model names
GEMINI_LITE_MODEL=gemini-2.0-flash-lite
GEMINI_FLASH_MODEL=gemini-1.5-flash
OLLAMA_MODEL=qwen2.5:1.5b
OLLAMA_URL=http://localhost:11434

# Cache
CACHE_TTL=60
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Running

```bash
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

### Optional: Ollama (Layer 3)
```bash
# Install Ollama: https://ollama.ai
ollama pull qwen2.5:1.5b
ollama serve  # runs on localhost:11434
```

## 🤖 Offline AI Model (Future Use)

For full offline support, add a local Qwen model using one of these options:

### Option 1 — GGUF (Recommended, ~350 MB total)
pip install llama-cpp-python
hf download Qwen/Qwen2.5-0.5B-Instruct-GGUF --local-dir ./models/qwen-gguf

### Option 2 — PyTorch CPU (~1.8 GB total)
pip install torch --index-url https://download.pytorch.org/whl/cpu
hf download Qwen/Qwen2.5-0.5B-Instruct --local-dir ./models/qwen

Note: If model is stored outside the project folder,
update model_path in pipeline/offline_model.py to the absolute path.

Current fallback chain: Groq → Gemini → sklearn (offline)

## API Endpoints

### POST /chat
Main chat endpoint. Requires JWT Bearer token.

**Request:**
```json
{
  "message": "مين أكتر طلاب غياباً؟",
  "model_config_data": {
    "enable_gemini_lite": true,
    "enable_gemini_flash": true,
    "enable_ollama": false,
    "enable_sklearn": true,
    "gemini_lite_model": "gemini-2.0-flash-lite",
    "gemini_flash_model": "gemini-1.5-flash",
    "ollama_model": "qwen2.5:1.5b",
    "ollama_url": "http://localhost:11434"
  }
}
```

**Response (unchanged):**
```json
{
  "reply": "📊 أكثر 5 طلاب غياباً: ...",
  "intent": "top_absentees",
  "entities": {}
}
```

> `model_config_data` is **optional**. If omitted, .env defaults are used.

### GET /chat/layers
Returns the current default layer configuration.

```json
{
  "layers": [
    {"name": "Gemini Lite", "model": "gemini-2.0-flash-lite", "type": "cloud"},
    {"name": "Gemini Flash", "model": "gemini-1.5-flash", "type": "cloud"},
    {"name": "Ollama", "model": "qwen2.5:1.5b", "type": "local"},
    {"name": "sklearn", "model": "TF-IDF + LogReg", "type": "builtin"}
  ],
  "defaults": { ... }
}
```

### GET /health
Health check.

## Per-Request Model Control (Dashboard Integration)

The admin can toggle AI layers directly from the dashboard chat widget.
Each request carries `model_config_data` — the backend respects it per-request.

See the **Frontend Instructions** section below for implementation details.

---

## Frontend Instructions (for dashboard developer)

### 1. Add to `api.js` — pass model config with chat requests

```javascript
// In your sendChatMessage function:
export const sendChatMessage = async (message, modelConfig = null) => {
    const payload = { message };
    if (modelConfig) {
        payload.model_config_data = modelConfig;
    }
    const response = await apiClient.post('/chat', payload);
    return response.data;
};

// Fetch available layers on mount:
export const getChatLayers = async () => {
    const response = await apiClient.get('/chat/layers');
    return response.data;
};
```

### 2. ChatWidget settings panel — UI description

Add a collapsible "AI Settings" gear icon button in the chat header.
When clicked, shows a panel with:

```
┌─────────────────────────────────────┐
│  ⚙️ AI Model Settings              │
├─────────────────────────────────────┤
│                                     │
│  ☁️ Gemini 2.0 Flash Lite   [ON]   │
│     Model: gemini-2.0-flash-lite    │
│                                     │
│  ☁️ Gemini 1.5 Flash        [ON]   │
│     Model: gemini-1.5-flash         │
│                                     │
│  🖥️ Ollama (Local)          [OFF]  │
│     Model: qwen2.5:1.5b            │
│     URL: http://localhost:11434     │
│                                     │
│  🧠 sklearn Fallback        [ON]   │
│     (Always available)              │
│                                     │
└─────────────────────────────────────┘
```

### 3. ChatWidget.jsx — settings state and toggle logic

```jsx
// Add to ChatWidget state:
const [showSettings, setShowSettings] = useState(false);
const [modelConfig, setModelConfig] = useState({
    enable_gemini_lite: true,
    enable_gemini_flash: true,
    enable_ollama: false,
    enable_sklearn: true,
    gemini_lite_model: "gemini-2.0-flash-lite",
    gemini_flash_model: "gemini-1.5-flash",
    ollama_model: "qwen2.5:1.5b",
    ollama_url: "http://localhost:11434",
});

// Fetch defaults on mount:
useEffect(() => {
    getChatLayers().then(data => {
        if (data.defaults) setModelConfig(data.defaults);
    }).catch(() => {});
}, []);

// Pass config when sending message:
const handleSend = async () => {
    const response = await sendChatMessage(message, modelConfig);
    // ... handle response
};

// Toggle handler:
const toggleLayer = (key) => {
    setModelConfig(prev => ({ ...prev, [key]: !prev[key] }));
};

// Settings panel JSX:
{showSettings && (
    <div className="chat-settings-panel">
        <h4>⚙️ AI Model Settings</h4>
        <label>
            <input type="checkbox" checked={modelConfig.enable_gemini_lite}
                   onChange={() => toggleLayer('enable_gemini_lite')} />
            ☁️ Gemini 2.0 Flash Lite
        </label>
        <label>
            <input type="checkbox" checked={modelConfig.enable_gemini_flash}
                   onChange={() => toggleLayer('enable_gemini_flash')} />
            ☁️ Gemini 1.5 Flash
        </label>
        <label>
            <input type="checkbox" checked={modelConfig.enable_ollama}
                   onChange={() => toggleLayer('enable_ollama')} />
            🖥️ Ollama (Local)
        </label>
        <label>
            <input type="checkbox" checked={modelConfig.enable_sklearn}
                   onChange={() => toggleLayer('enable_sklearn')} />
            🧠 sklearn Fallback
        </label>
    </div>
)}
```

### 4. Settings gear button (in chat header)

```jsx
<button className="chat-settings-btn" onClick={() => setShowSettings(!showSettings)}>
    <Settings size={16} />
</button>
```

---

## License

Part of the Arak School Management Suite. Created by Ahmed Saady.
