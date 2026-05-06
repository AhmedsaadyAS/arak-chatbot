"""
Multi-Layer AI Service for Arak Chatbot.

Fallback chain:
  Layer 1 — Gemini 2.0 Flash Lite  (cloud, fastest)
  Layer 2 — Gemini 1.5 Flash       (cloud, secondary)
  Layer 3 — Ollama + Qwen 2.5 1.5B (local, offline)
  Layer 4 — sklearn TF-IDF         (always available, last resort)

Each layer can be enabled/disabled per-request via ModelConfig.
Results are cached in-memory for CACHE_TTL seconds.
"""

import os
import json
import time
import asyncio
from typing import Optional

import httpx
from google import genai
from google.genai import types
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# ── .env defaults ────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

DEFAULT_ENABLE_GEMINI_LITE = os.getenv("ENABLE_GEMINI_LITE", "true").lower() == "true"
DEFAULT_ENABLE_GEMINI_FLASH = os.getenv("ENABLE_GEMINI_FLASH", "true").lower() == "true"
DEFAULT_ENABLE_OLLAMA = os.getenv("ENABLE_OLLAMA", "true").lower() == "true"
DEFAULT_ENABLE_SKLEARN = os.getenv("ENABLE_SKLEARN", "true").lower() == "true"

DEFAULT_GEMINI_LITE_MODEL = os.getenv("GEMINI_LITE_MODEL", "gemini-2.0-flash-lite")
DEFAULT_GEMINI_FLASH_MODEL = os.getenv("GEMINI_FLASH_MODEL", "gemini-1.5-flash")
DEFAULT_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:1.5b")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

CACHE_TTL = int(os.getenv("CACHE_TTL", "60"))

# ── Prompts ──────────────────────────────────────────────────────────

INTENT_DEFINITIONS = """
You are an intent classifier for a school management system called "Arak".
Classify the user's message into exactly ONE of these intents:

1. "attendance_query" — asking about attendance/absence for a class or student (e.g. "من غاب اليوم", "حضور الفصل 1")
2. "student_grade" — asking about grades/scores/evaluations for a specific student (e.g. "درجات الطالب 5", "نتيجة أحمد")
3. "schedule_query" — asking about class timetable/schedule (e.g. "جدول الحصص", "متى حصة الرياضيات")
4. "top_absentees" — asking about most absent students overall (e.g. "مين أكتر طلاب غياباً", "who has the most absences")
5. "weak_students" — asking about low-performing students (e.g. "الطلاب الضعفاء", "students with low grades")
6. "class_summary" — asking for an overall summary of a class (e.g. "ملخص الفصل 1", "class 2 overview")
7. "unpaid_fees" — asking about unpaid fees (e.g. "كام طالب ما دفعوش", "unpaid fees list")
8. "daily_summary" — asking for today's summary (e.g. "ملخص النهارده", "today's summary")
9. "fee_status" — asking about a specific student's fee status
10. "task_status" — asking about tasks/assignments
11. "event_query" — asking about upcoming events
12. "class_info" — asking about class information/details
13. "teacher_query" — asking about teacher information
14. "greeting" — a greeting or hello
15. "fallback" — anything else that doesn't match

Reply with ONLY a JSON object: {"intent": "<intent_name>"}
"""

ANALYSIS_SYSTEM_PROMPT = """
أنت مساعد ذكي لنظام إدارة مدرسة "أراك". ترد بالعربية دائمًا.
- كن مختصرًا ومفيدًا
- استخدم الأرقام والإحصائيات من البيانات المقدمة
- قدّم توصيات عملية عند الإمكان
- لا تخترع بيانات — استخدم فقط ما هو مقدم لك
- نسّق الردود بشكل واضح مع رموز emoji مناسبة
"""


# ── Per-request model config ─────────────────────────────────────────

class ModelConfig(BaseModel):
    enable_gemini_lite: bool = DEFAULT_ENABLE_GEMINI_LITE
    enable_gemini_flash: bool = DEFAULT_ENABLE_GEMINI_FLASH
    enable_ollama: bool = DEFAULT_ENABLE_OLLAMA
    enable_sklearn: bool = DEFAULT_ENABLE_SKLEARN
    gemini_lite_model: str = DEFAULT_GEMINI_LITE_MODEL
    gemini_flash_model: str = DEFAULT_GEMINI_FLASH_MODEL
    ollama_model: str = DEFAULT_OLLAMA_MODEL
    ollama_url: str = DEFAULT_OLLAMA_URL


# ── In-memory cache ──────────────────────────────────────────────────

_cache: dict[str, tuple[float, str]] = {}


def _cache_get(key: str) -> Optional[str]:
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    if entry:
        del _cache[key]
    return None


def _cache_set(key: str, value: str):
    _cache[key] = (time.time(), value)


# ── sklearn fallback classifier ──────────────────────────────────────

_sklearn_classifier = None
_sklearn_loaded = False


def _load_sklearn():
    global _sklearn_classifier, _sklearn_loaded
    if _sklearn_loaded:
        return _sklearn_classifier
    _sklearn_loaded = True
    try:
        from pipeline.intent_classifier import IntentClassifier
        clf = IntentClassifier()
        clf.load()
        _sklearn_classifier = clf
        print("[Chatbot] sklearn classifier loaded as Layer 4 fallback")
    except Exception as e:
        print(f"[Chatbot] sklearn classifier unavailable: {e}")
        _sklearn_classifier = None
    return _sklearn_classifier


def _sklearn_classify(message: str) -> str:
    clf = _load_sklearn()
    if clf is None:
        return "fallback"
    try:
        intent, confidence = clf.predict(message)
        print(f"[Chatbot] sklearn prediction: {intent} ({confidence:.2f})")
        if confidence < 0.3:
            return "fallback"
        return intent
    except Exception as e:
        print(f"[Chatbot] sklearn error: {e}")
        return "fallback"


# ── Helper: check if error is quota/rate-limit ───────────────────────

def _is_quota_error(error: Exception) -> bool:
    err_str = str(error)
    return "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower()


# ── Gemini call ──────────────────────────────────────────────────────

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


async def _call_gemini(model: str, contents: str, temperature: float, max_tokens: int) -> str:
    client = _get_gemini_client()
    if client is None:
        raise RuntimeError("GEMINI_API_KEY not set")

    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text.strip()


# ── Ollama call ──────────────────────────────────────────────────────

async def _call_ollama(model: str, url: str, prompt: str, temperature: float) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{url}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()
    return data.get("response", "").strip()


# ── Multi-layer orchestrator ─────────────────────────────────────────

async def _run_layers(
    config: ModelConfig,
    contents: str,
    temperature: float,
    max_tokens: int,
    task: str = "classify",
) -> str:
    """Try each enabled layer in order. Only fallback on quota errors."""

    layers = []
    if config.enable_gemini_lite:
        layers.append(("Gemini Lite", "gemini", config.gemini_lite_model))
    if config.enable_gemini_flash:
        layers.append(("Gemini Flash", "gemini", config.gemini_flash_model))
    if config.enable_ollama:
        layers.append(("Ollama", "ollama", config.ollama_model))

    last_error = None

    for name, provider, model in layers:
        try:
            if provider == "gemini":
                result = await _call_gemini(model, contents, temperature, max_tokens)
            else:
                result = await _call_ollama(model, config.ollama_url, contents, temperature)

            print(f"[Chatbot] Using layer: {name} ({model})")
            return result

        except Exception as e:
            last_error = e
            if _is_quota_error(e):
                print(f"[Chatbot] {name} quota exceeded, falling back...")
                continue
            # Non-quota error → raise immediately
            raise

    # All cloud/local layers exhausted — try sklearn for classify only
    if task == "classify" and config.enable_sklearn:
        print("[Chatbot] Using layer: sklearn (fallback)")
        # For sklearn, we need the original message, not the full prompt
        # The caller will handle this case via the return value
        raise _AllLayersExhausted(str(last_error) if last_error else "All layers disabled")

    raise RuntimeError(
        f"All AI layers exhausted. Last error: {last_error}"
        if last_error
        else "No AI layers enabled in config."
    )


class _AllLayersExhausted(Exception):
    """Signal that all cloud/local layers failed — sklearn should be tried."""
    pass


# ── Public API ───────────────────────────────────────────────────────

class AIService:
    """Stateless service — all state is module-level for easy reuse."""

    async def classify_intent(self, message: str, config: Optional[ModelConfig] = None) -> tuple[str, str]:
        """
        Classify intent with multi-layer fallback.
        Returns (intent, layer_used).
        """
        cfg = config or ModelConfig()

        # Cache check
        cache_key = f"classify:{message}"
        cached = _cache_get(cache_key)
        if cached:
            print("[Chatbot] Using layer: cache")
            return cached, "cache"

        contents = f"{INTENT_DEFINITIONS}\n\nUser message: {message}"

        try:
            text = await _run_layers(cfg, contents, temperature=0.0, max_tokens=50, task="classify")
            intent = _parse_intent_json(text)
            _cache_set(cache_key, intent)
            return intent, "cloud"

        except _AllLayersExhausted:
            # sklearn fallback
            if cfg.enable_sklearn:
                intent = _sklearn_classify(message)
                _cache_set(cache_key, intent)
                return intent, "sklearn"
            return "fallback", "none"

        except Exception as e:
            print(f"[Chatbot] classify error: {e}")
            # Try sklearn as absolute last resort
            if cfg.enable_sklearn:
                intent = _sklearn_classify(message)
                return intent, "sklearn"
            return "fallback", "none"

    async def analyze_data(self, prompt: str, data: dict, config: Optional[ModelConfig] = None) -> str:
        cfg = config or ModelConfig()

        cache_key = f"analyze:{hash(prompt + json.dumps(data, ensure_ascii=False, default=str))}"
        cached = _cache_get(cache_key)
        if cached:
            print("[Chatbot] Using layer: cache")
            return cached

        full_prompt = (
            f"{ANALYSIS_SYSTEM_PROMPT}\n\n{prompt}\n\n"
            f"البيانات:\n{json.dumps(data, ensure_ascii=False, default=str)}"
        )

        try:
            result = await _run_layers(cfg, full_prompt, temperature=0.3, max_tokens=1000, task="analyze")
            _cache_set(cache_key, result)
            return result
        except Exception as e:
            print(f"[Chatbot] analyze error: {e}")
            return "حدث خطأ أثناء تحليل البيانات. يرجى المحاولة مرة أخرى."

    async def format_response(
        self, intent: str, raw_data, user_message: str, config: Optional[ModelConfig] = None
    ) -> str:
        cfg = config or ModelConfig()

        data_str = json.dumps(raw_data, ensure_ascii=False, default=str)[:3000]
        cache_key = f"format:{intent}:{hash(data_str + user_message)}"
        cached = _cache_get(cache_key)
        if cached:
            print("[Chatbot] Using layer: cache")
            return cached

        prompt = (
            f'{ANALYSIS_SYSTEM_PROMPT}\n\n'
            f'المستخدم سأل: "{user_message}"\n'
            f'نوع الطلب: {intent}\n'
            f'البيانات المسترجعة من النظام:\n{data_str}\n\n'
            f'قم بتنسيق هذه البيانات كرد واضح ومفيد بالعربية. استخدم emoji مناسبة.'
        )

        try:
            result = await _run_layers(cfg, prompt, temperature=0.3, max_tokens=800, task="format")
            _cache_set(cache_key, result)
            return result
        except Exception as e:
            print(f"[Chatbot] format error: {e}")
            return str(raw_data)

    def get_active_layers(self, config: Optional[ModelConfig] = None) -> list[dict]:
        """Return list of active layers for status/debugging."""
        cfg = config or ModelConfig()
        layers = []
        if cfg.enable_gemini_lite:
            layers.append({"name": "Gemini Lite", "model": cfg.gemini_lite_model, "type": "cloud"})
        if cfg.enable_gemini_flash:
            layers.append({"name": "Gemini Flash", "model": cfg.gemini_flash_model, "type": "cloud"})
        if cfg.enable_ollama:
            layers.append({"name": "Ollama", "model": cfg.ollama_model, "type": "local"})
        if cfg.enable_sklearn:
            layers.append({"name": "sklearn", "model": "TF-IDF + LogReg", "type": "builtin"})
        return layers


def _parse_intent_json(text: str) -> str:
    if "{" in text:
        try:
            json_str = text[text.index("{"):text.rindex("}") + 1]
            result = json.loads(json_str)
            return result.get("intent", "fallback")
        except (json.JSONDecodeError, ValueError):
            pass
    return "fallback"
