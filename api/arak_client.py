import httpx
import os
from typing import Dict, Any, Optional

class ArakClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("ARAK_API_URL", "http://localhost:5000/api")

    async def call_api(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None, data: Optional[Dict] = None, token: Optional[str] = None) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"} if token else {}
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.request(method, f"{self.base_url}/{endpoint}", params=params, json=data, headers=headers)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"API Error: {str(e)}")
                return {"error": str(e)}

    # 1. Attendance - Endpoint: GET /api/Attendance/class/{classId}
    async def get_attendance_by_class(self, class_id: int, token: str):
        return await self.call_api(f"Attendance/class/{class_id}", token=token)

    # 2. Evaluations - لا يوجد Endpoint مباشر للـ studentId في Swagger
    async def get_student_grades(self, student_id: int, token: str):
        data = await self.call_api("Evaluations", token=token)
        if isinstance(data, list):
            # فلترة النتائج محلياً
            return [e for e in data if str(e.get("studentId")) == str(student_id)]
        return {"error": "لا توجد بيانات درجات متاحة."}

    # 3. Classes - لعمل الـ Lookup
    async def get_classes(self, token: str):
        return await self.call_api("Classes", token=token)

    # 4. Formatter محسن
    def format_attendance(self, data: Any) -> str:
        if isinstance(data, list) and data:
            present = len([x for x in data if x.get("status") == "Present"])
            absent = len([x for x in data if x.get("status") == "Absent"])
            return f"تقرير الحضور: ✅ {present} حاضر، ❌ {absent} غائب."
        return "لم أتمكن من العثور على سجلات حضور لهذا الفصل."

    def format_grades(self, data: Any) -> str:
        if isinstance(data, list) and data:
            return "\n".join([f"- {g.get('subjectName', 'مادة')}: {g.get('grade', 'N/A')}" for g in data])
        return "لا توجد درجات مسجلة لهذا الطالب."