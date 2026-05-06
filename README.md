# Arak AI Chatbot v2.0

An intelligent assistant for the **Arak School Admin System**, powered by **Google Gemini AI** with role-based access control (RBAC).

## Overview

The Arak Chatbot is a FastAPI-based microservice that integrates with the main Arak Backend (ASP.NET Core). It uses Google Gemini for intent classification and response generation, providing:

### Basic Queries
- **Attendance Tracking:** Query daily attendance by class or student
- **Academic Performance:** Retrieve student grades and evaluations
- **Schedules:** Fetch class timetables
- **Fees:** Check student fee payment status
- **Tasks:** View assignment status
- **Events:** List upcoming school events

### Analytical Intents (NEW in v2.0)
- **Top Absentees:** "مين أكتر طلاب غياباً؟" — identifies students with most absences + recommendations
- **Weak Students:** "الطلاب الضعفاء في الرياضيات؟" — finds students scoring below 50 + recommendations
- **Class Summary:** "ملخص الفصل 1" — comprehensive class report (attendance + grades + tasks)
- **Unpaid Fees:** "كام طالب ما دفعوش؟" — lists students with outstanding fees
- **Daily Summary:** "ملخص النهارده" — today's attendance + events overview

## Tech Stack

- **Framework:** FastAPI (Python 3.9+)
- **AI Engine:** Google Gemini 2.0 Flash
- **API Client:** Httpx (Async HTTP)
- **Authentication:** JWT (Bearer Token)
- **Integration:** Arak Backend (.NET 9) + Arak Dashboard (React)

## RBAC (Role-Based Access Control)

| Role | Allowed Intents |
|------|----------------|
| Super Admin / Admin | All intents |
| Teacher | Attendance, Grades, Schedule, Top Absentees, Weak Students, Class Summary, Tasks, Daily Summary |
| Parent | Attendance (own children), Grades, Fees, Schedule, Events |
| Student | Blocked (polite refusal) |

## Project Structure

```text
arak-chatbot/
├── api/
│   ├── chat_router.py        # Main chat endpoint + RBAC + intent handlers
│   ├── gemini_service.py     # Gemini AI integration (classify + analyze + format)
│   ├── arak_client.py        # HTTP client for Arak Backend API
│   └── auth_middleware.py    # JWT authentication
├── data/
│   └── intents.json          # Training data (legacy, kept for reference)
├── models/                   # Legacy sklearn models (no longer used)
├── pipeline/                 # Legacy NLP pipeline (no longer used)
├── main.py                   # Application entry point
└── requirements.txt
```

## Configuration

1. **Environment Variables** — create `.env` in root:
   ```env
   ARAK_API_URL=http://localhost:5000/api
   JWT_SECRET_KEY=your_jwt_secret_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

2. **Get a Gemini API Key:**
   - Go to [Google AI Studio](https://aistudio.google.com)
   - Create a free API key
   - Add it to `.env` as `GEMINI_API_KEY`

3. **Installation:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. **Running:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 --reload
   ```

## API Endpoints

### POST /chat
Main chatbot endpoint. Requires JWT Bearer token.

**Request:**
```json
{
  "message": "مين أكتر طلاب غياباً؟"
}
```

**Response:**
```json
{
  "reply": "📊 أكثر 5 طلاب غياباً:\n1. أحمد — 12 يوم ...",
  "intent": "top_absentees",
  "entities": {}
}
```

**Headers:**
```
Authorization: Bearer <jwt_token>
```

### GET /health
Health check endpoint.

## How It Works

1. User sends message with JWT token
2. JWT is validated → role and userId extracted
3. RBAC check: is this role allowed to ask this type of question?
4. Gemini classifies the message into one of 15 intents
5. Entities extracted (studentId, classId, subjectName) via regex
6. Relevant data fetched from Arak Backend API
7. For analytical intents: Gemini analyzes the data and provides insights in Arabic
8. For simple queries: Gemini formats the raw data into a clean Arabic response

## Migration from v1.0

v2.0 replaces the sklearn TF-IDF + Logistic Regression classifier with Google Gemini. The legacy `pipeline/` and `models/` directories are kept for reference but are no longer imported. Key improvements:
- Much better intent classification accuracy (especially for Arabic)
- Natural language responses instead of template strings
- Analytical capabilities (data analysis + recommendations)
- RBAC enforcement

## License

Part of the Arak School Management Suite. Created by Ahmed Saady.
