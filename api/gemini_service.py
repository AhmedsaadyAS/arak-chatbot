import os
import json
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME = "gemini-2.0-flash"

# Intent definitions for Gemini to classify
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


MAX_RETRIES = 2
RETRY_DELAYS = [2, 5]


class GeminiService:
    def __init__(self):
        if GEMINI_API_KEY:
            self.client = genai.Client(api_key=GEMINI_API_KEY)
        else:
            self.client = None
            print("WARNING: GEMINI_API_KEY not set — Gemini features disabled")

    async def _call_gemini(self, contents: str, temperature: float = 0.0, max_tokens: int = 50) -> str:
        """Call Gemini with retry on 429 rate-limit errors."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                return response.text.strip()
            except Exception as e:
                err_str = str(e)
                if "429" in err_str and attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAYS[attempt])
                    continue
                raise

    async def classify_intent(self, message: str) -> str:
        if not self.client:
            return "fallback"
        try:
            text = await self._call_gemini(
                f"{INTENT_DEFINITIONS}\n\nUser message: {message}",
                temperature=0.0,
                max_tokens=50,
            )
            if "{" in text:
                json_str = text[text.index("{"):text.rindex("}") + 1]
                result = json.loads(json_str)
                return result.get("intent", "fallback")
            return "fallback"
        except Exception as e:
            print(f"Gemini classify error: {e}")
            return "fallback"

    async def analyze_data(self, prompt: str, data: dict) -> str:
        if not self.client:
            return "خدمة Gemini غير متاحة حاليًا."
        try:
            full_prompt = f"{ANALYSIS_SYSTEM_PROMPT}\n\n{prompt}\n\nالبيانات:\n{json.dumps(data, ensure_ascii=False, default=str)}"
            return await self._call_gemini(full_prompt, temperature=0.3, max_tokens=1000)
        except Exception as e:
            print(f"Gemini analyze error: {e}")
            return "حدث خطأ أثناء تحليل البيانات. يرجى المحاولة مرة أخرى."

    async def format_response(self, intent: str, raw_data, user_message: str) -> str:
        if not self.client:
            return str(raw_data)
        try:
            prompt = f"""المستخدم سأل: "{user_message}"
نوع الطلب: {intent}
البيانات المسترجعة من النظام:
{json.dumps(raw_data, ensure_ascii=False, default=str)[:3000]}

قم بتنسيق هذه البيانات كرد واضح ومفيد بالعربية. استخدم emoji مناسبة."""

            return await self._call_gemini(
                f"{ANALYSIS_SYSTEM_PROMPT}\n\n{prompt}",
                temperature=0.3,
                max_tokens=800,
            )
        except Exception as e:
            print(f"Gemini format error: {e}")
            return str(raw_data)
