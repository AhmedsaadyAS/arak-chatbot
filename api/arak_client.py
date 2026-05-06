import httpx
import os
from datetime import date
from typing import Dict, Any, List, Optional

class ArakClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("ARAK_API_URL", "http://localhost:5000/api")

    async def call_api(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None, token: Optional[str] = None) -> Any:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"} if token else {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.request(method, f"{self.base_url}/{endpoint}", params=params, json=data, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"API Error [{endpoint}]: {str(e)}")
                return {"error": str(e)}

    # ── Existing endpoints ──────────────────────────────────────────

    async def get_attendance_by_class(self, class_id: int, token: str, date_str: str = None):
        params = {"date": date_str} if date_str else None
        return await self.call_api(f"Attendance/class/{class_id}", params=params, token=token)

    async def get_student_grades(self, student_id: int, token: str):
        data = await self.call_api("Evaluations", token=token)
        if isinstance(data, list):
            return [e for e in data if str(e.get("studentId")) == str(student_id)]
        return {"error": "لا توجد بيانات درجات متاحة."}

    async def get_classes(self, token: str):
        return await self.call_api("Classes", token=token)

    async def get_schedules_by_class(self, class_id: int, token: str):
        return await self.call_api("Schedules", params={"classId": class_id}, token=token)

    # ── New endpoints for analytical intents ─────────────────────────

    async def get_all_students(self, token: str):
        return await self.call_api("Students", token=token)

    async def get_all_evaluations(self, token: str):
        return await self.call_api("Evaluations", token=token)

    async def get_all_fees(self, token: str):
        return await self.call_api("Fees", token=token)

    async def get_events(self, token: str):
        return await self.call_api("Events", token=token)

    async def get_all_teachers(self, token: str):
        return await self.call_api("Teachers", token=token)

    async def get_all_tasks(self, token: str):
        return await self.call_api("Tasks", token=token)

    async def get_student_attendance(self, student_id: int, token: str, month: int = None, year: int = None):
        params = {}
        if month: params["month"] = month
        if year: params["year"] = year
        return await self.call_api(f"Attendance/student/{student_id}", params=params, token=token)

    # ── Formatters ──────────────────────────────────────────────────

    def format_attendance(self, data: Any) -> str:
        if isinstance(data, dict) and "students" in data:
            students = data["students"]
            present = len([x for x in students if x.get("status") == "Present" or x.get("status") == 0])
            absent = len([x for x in students if x.get("status") == "Absent" or x.get("status") == 1])
            late = len([x for x in students if x.get("status") == "Late" or x.get("status") == 2])
            total = len(students)
            return f"تقرير الحضور: إجمالي {total} طالب — ✅ {present} حاضر، ❌ {absent} غائب، ⏰ {late} متأخر."
        if isinstance(data, list) and data:
            present = len([x for x in data if x.get("status") in ("Present", 0)])
            absent = len([x for x in data if x.get("status") in ("Absent", 1)])
            return f"تقرير الحضور: ✅ {present} حاضر، ❌ {absent} غائب."
        return "لم أتمكن من العثور على سجلات حضور لهذا الفصل."

    def format_grades(self, data: Any) -> str:
        if isinstance(data, list) and data:
            return "\n".join([f"- {g.get('subjectName', 'مادة')}: {g.get('grade', 'N/A')}" for g in data])
        return "لا توجد درجات مسجلة لهذا الطالب."
