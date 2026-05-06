from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.arak_client import ArakClient
from api.gemini_service import GeminiService
from api.auth_middleware import get_current_user
import re
from datetime import date
from typing import Dict, Any, Optional

router = APIRouter()
arak_client = ArakClient()
gemini = GeminiService()

# ── RBAC Configuration ─────────────────────────────────────────────

ROLE_PERMISSIONS = {
    "Super Admin": "*",  # all intents
    "Admin": "*",
    "Academic Admin": "*",
    "Teacher": [
        "attendance_query", "student_grade", "schedule_query",
        "top_absentees", "weak_students", "class_summary",
        "task_status", "class_info", "teacher_query",
        "greeting", "daily_summary",
    ],
    "Parent": [
        "attendance_query", "student_grade", "fee_status",
        "schedule_query", "event_query", "greeting",
    ],
}

BLOCKED_ROLES = {"Student"}


class ChatRequest(BaseModel):
    message: str
    token: Optional[str] = None


def check_rbac(role: str, intent: str) -> bool:
    if role in BLOCKED_ROLES:
        return False
    perms = ROLE_PERMISSIONS.get(role, [])
    if perms == "*":
        return True
    return intent in perms


def extract_entities(text: str) -> Dict[str, Any]:
    entities = {}
    lowered = text.lower()

    # Student ID
    s_match = re.search(r"(student|طالب|id)[^\d]{0,10}(\d+)", lowered)
    if s_match:
        entities["studentId"] = int(s_match.group(2))

    # Class ID or name
    c_match = re.search(r"(class|الفصل|فصل|صف|grade)[^\d]{0,10}(\d+[-a-z]?)", lowered)
    if c_match:
        val = c_match.group(2)
        if val.isdigit():
            entities["classId"] = int(val)
        else:
            entities["classLookup"] = val

    # Subject name (Arabic or English)
    subj_match = re.search(
        r"(مادة|subject|في)\s+([\u0600-\u06FF\w]+)",
        lowered,
    )
    if subj_match:
        entities["subjectName"] = subj_match.group(2)

    return entities


async def _resolve_class_id(lookup: str, token: str):
    classes = await arak_client.get_classes(token=token)
    if isinstance(classes, list):
        for c in classes:
            if lookup in str(c.get("name", "")).lower() or lookup in str(c.get("grade", "")).lower():
                return c.get("id")
    return None


# ── Intent Handlers ─────────────────────────────────────────────────

async def handle_attendance_query(entities: Dict, token: str, message: str) -> str:
    cid = entities.get("classId")
    if not cid and entities.get("classLookup"):
        cid = await _resolve_class_id(entities["classLookup"], token)
    if cid:
        data = await arak_client.get_attendance_by_class(cid, token)
        if isinstance(data, dict) and "error" in data:
            return "لم أتمكن من جلب بيانات الحضور. تأكد من رقم الفصل."
        return await gemini.format_response("attendance_query", data, message)
    return "من فضلك حدد رقم الفصل (مثال: غياب الفصل 1)."


async def handle_student_grade(entities: Dict, token: str, message: str) -> str:
    sid = entities.get("studentId")
    if sid:
        data = await arak_client.get_student_grades(sid, token)
        if isinstance(data, list) and data:
            return await gemini.format_response("student_grade", data, message)
        return "لا توجد درجات مسجلة لهذا الطالب."
    return "من فضلك حدد رقم الطالب (مثال: درجات الطالب 5)."


async def handle_schedule_query(entities: Dict, token: str, message: str) -> str:
    cid = entities.get("classId")
    if not cid and entities.get("classLookup"):
        cid = await _resolve_class_id(entities["classLookup"], token)
    if cid:
        data = await arak_client.get_schedules_by_class(cid, token)
        if isinstance(data, list) and data:
            return await gemini.format_response("schedule_query", data, message)
        return "لا يوجد جدول حصص لهذا الفصل."
    return "من فضلك حدد رقم الفصل (مثال: جدول الفصل 1)."


async def handle_top_absentees(token: str, message: str) -> str:
    """Find students with the most absences."""
    classes = await arak_client.get_classes(token=token)
    if not isinstance(classes, list):
        return "لم أتمكن من جلب بيانات الفصول."

    absence_counts = {}
    for cls in classes[:10]:  # Limit to avoid too many API calls
        cid = cls.get("id")
        if not cid:
            continue
        att_data = await arak_client.get_attendance_by_class(cid, token)
        students = []
        if isinstance(att_data, dict) and "students" in att_data:
            students = att_data["students"]
        elif isinstance(att_data, list):
            students = att_data
        for s in students:
            status = s.get("status")
            if status in ("Absent", 1):
                name = s.get("studentName", s.get("name", f"طالب {s.get('studentId', '?')}"))
                sid = s.get("studentId", name)
                absence_counts[sid] = {
                    "name": name,
                    "count": absence_counts.get(sid, {}).get("count", 0) + 1,
                }

    if not absence_counts:
        return "لا توجد سجلات غياب حاليًا."

    top_5 = sorted(absence_counts.values(), key=lambda x: x["count"], reverse=True)[:5]
    return await gemini.analyze_data(
        "حلل بيانات أكثر الطلاب غيابًا وقدم توصيات لتحسين الحضور:",
        {"top_absentees": top_5},
    )


async def handle_weak_students(entities: Dict, token: str, message: str) -> str:
    """Find students with low grades (below 50)."""
    evals = await arak_client.get_all_evaluations(token)
    if not isinstance(evals, list):
        return "لم أتمكن من جلب بيانات التقييمات."

    subject_filter = entities.get("subjectName")
    weak = []
    for e in evals:
        grade = e.get("grade")
        if grade is None:
            continue
        try:
            grade_val = float(grade)
        except (ValueError, TypeError):
            continue
        if grade_val < 50:
            if subject_filter and subject_filter.lower() not in str(e.get("subjectName", "")).lower():
                continue
            weak.append({
                "studentName": e.get("studentName", f"طالب {e.get('studentId', '?')}"),
                "subject": e.get("subjectName", "غير محدد"),
                "grade": grade_val,
            })

    if not weak:
        return "لا يوجد طلاب بدرجات أقل من 50 حاليًا. 🎉"

    weak.sort(key=lambda x: x["grade"])
    return await gemini.analyze_data(
        "حلل بيانات الطلاب ذوي الأداء الضعيف (أقل من 50 درجة) وقدم توصيات:",
        {"weak_students": weak[:20], "total_count": len(weak)},
    )


async def handle_class_summary(entities: Dict, token: str, message: str) -> str:
    """Comprehensive class summary: attendance + grades + tasks."""
    cid = entities.get("classId")
    if not cid and entities.get("classLookup"):
        cid = await _resolve_class_id(entities["classLookup"], token)
    if not cid:
        return "من فضلك حدد رقم الفصل (مثال: ملخص الفصل 1)."

    # Parallel data fetching
    attendance = await arak_client.get_attendance_by_class(cid, token)
    evaluations = await arak_client.get_all_evaluations(token)
    tasks = await arak_client.get_all_tasks(token)

    # Filter evaluations and tasks for this class
    class_evals = []
    if isinstance(evaluations, list):
        class_evals = [e for e in evaluations if str(e.get("classId")) == str(cid)]

    class_tasks = []
    if isinstance(tasks, list):
        class_tasks = [t for t in tasks if str(t.get("classId")) == str(cid)]

    summary_data = {
        "classId": cid,
        "attendance": attendance if not isinstance(attendance, dict) or "error" not in attendance else {},
        "evaluations_count": len(class_evals),
        "evaluations_sample": class_evals[:10],
        "tasks_count": len(class_tasks),
        "tasks_sample": class_tasks[:5],
    }

    return await gemini.analyze_data(
        f"قدم ملخصًا شاملًا للفصل رقم {cid} يشمل: الحضور، الدرجات، المهام، وتوصيات لتحسين الأداء:",
        summary_data,
    )


async def handle_unpaid_fees(token: str, message: str) -> str:
    """Find students with unpaid fees."""
    fees = await arak_client.get_all_fees(token)
    if not isinstance(fees, list):
        return "لم أتمكن من جلب بيانات الرسوم."

    unpaid = [
        {
            "studentName": f.get("studentName", f"طالب {f.get('studentId', '?')}"),
            "amount": f.get("amount", 0),
            "dueDate": f.get("dueDate", ""),
            "status": f.get("status", ""),
        }
        for f in fees
        if str(f.get("status", "")).lower() in ("unpaid", "pending", "overdue", "0", "false")
        or f.get("isPaid") is False
    ]

    if not unpaid:
        return "جميع الرسوم مدفوعة! ✅"

    return await gemini.analyze_data(
        "حلل بيانات الرسوم غير المدفوعة وقدم ملخصًا:",
        {"unpaid_fees": unpaid[:20], "total_unpaid": len(unpaid)},
    )


async def handle_daily_summary(token: str, message: str) -> str:
    """Today's summary: attendance + events."""
    today = date.today().isoformat()

    classes = await arak_client.get_classes(token=token)
    events = await arak_client.get_events(token)

    # Get attendance for all classes today
    attendance_summary = []
    if isinstance(classes, list):
        for cls in classes[:10]:
            cid = cls.get("id")
            if not cid:
                continue
            att = await arak_client.get_attendance_by_class(cid, token, date_str=today)
            students = []
            if isinstance(att, dict) and "students" in att:
                students = att["students"]
            elif isinstance(att, list):
                students = att

            present = len([s for s in students if s.get("status") in ("Present", 0)])
            absent = len([s for s in students if s.get("status") in ("Absent", 1)])
            if students:
                attendance_summary.append({
                    "class": cls.get("name", f"فصل {cid}"),
                    "total": len(students),
                    "present": present,
                    "absent": absent,
                })

    today_events = []
    if isinstance(events, list):
        today_events = [e for e in events if today in str(e.get("date", ""))]

    summary_data = {
        "date": today,
        "attendance": attendance_summary,
        "events": today_events[:5],
    }

    return await gemini.analyze_data(
        f"قدم ملخص اليوم ({today}) للمدرسة يشمل: إجمالي الحضور والغياب لكل فصل، والأحداث المقررة:",
        summary_data,
    )


async def handle_fee_status(entities: Dict, token: str, message: str) -> str:
    sid = entities.get("studentId")
    fees = await arak_client.get_all_fees(token)
    if not isinstance(fees, list):
        return "لم أتمكن من جلب بيانات الرسوم."
    if sid:
        student_fees = [f for f in fees if str(f.get("studentId")) == str(sid)]
        if student_fees:
            return await gemini.format_response("fee_status", student_fees, message)
        return f"لا توجد رسوم مسجلة للطالب رقم {sid}."
    return "من فضلك حدد رقم الطالب (مثال: رسوم الطالب 5)."


async def handle_task_status(entities: Dict, token: str, message: str) -> str:
    tasks = await arak_client.get_all_tasks(token)
    if not isinstance(tasks, list):
        return "لم أتمكن من جلب المهام."
    cid = entities.get("classId")
    if cid:
        tasks = [t for t in tasks if str(t.get("classId")) == str(cid)]
    if tasks:
        return await gemini.format_response("task_status", tasks[:15], message)
    return "لا توجد مهام حاليًا."


async def handle_event_query(token: str, message: str) -> str:
    events = await arak_client.get_events(token)
    if isinstance(events, list) and events:
        return await gemini.format_response("event_query", events[:10], message)
    return "لا توجد أحداث مسجلة حاليًا."


async def handle_class_info(entities: Dict, token: str, message: str) -> str:
    classes = await arak_client.get_classes(token=token)
    if isinstance(classes, list) and classes:
        cid = entities.get("classId")
        if cid:
            cls = next((c for c in classes if c.get("id") == cid), None)
            if cls:
                return await gemini.format_response("class_info", cls, message)
            return f"الفصل رقم {cid} غير موجود."
        return await gemini.format_response("class_info", classes, message)
    return "لم أتمكن من جلب بيانات الفصول."


async def handle_teacher_query(token: str, message: str) -> str:
    teachers = await arak_client.get_all_teachers(token)
    if isinstance(teachers, list) and teachers:
        return await gemini.format_response("teacher_query", teachers[:15], message)
    return "لم أتمكن من جلب بيانات المعلمين."


# ── Intent → Handler mapping ────────────────────────────────────────

INTENT_HANDLERS = {
    "attendance_query": lambda e, t, m: handle_attendance_query(e, t, m),
    "student_grade":    lambda e, t, m: handle_student_grade(e, t, m),
    "schedule_query":   lambda e, t, m: handle_schedule_query(e, t, m),
    "top_absentees":    lambda e, t, m: handle_top_absentees(t, m),
    "weak_students":    lambda e, t, m: handle_weak_students(e, t, m),
    "class_summary":    lambda e, t, m: handle_class_summary(e, t, m),
    "unpaid_fees":      lambda e, t, m: handle_unpaid_fees(t, m),
    "daily_summary":    lambda e, t, m: handle_daily_summary(t, m),
    "fee_status":       lambda e, t, m: handle_fee_status(e, t, m),
    "task_status":      lambda e, t, m: handle_task_status(e, t, m),
    "event_query":      lambda e, t, m: handle_event_query(t, m),
    "class_info":       lambda e, t, m: handle_class_info(e, t, m),
    "teacher_query":    lambda e, t, m: handle_teacher_query(t, m),
}


@router.post("/chat")
async def chat(request: ChatRequest, user: Dict[str, Any] = Depends(get_current_user)):
    msg = request.message
    token = user.get("token", "")
    role = user.get("role", "")

    # Block Student role
    if role in BLOCKED_ROLES:
        return {
            "reply": "عذرًا، هذه الخدمة غير متاحة للطلاب حاليًا. يرجى التواصل مع إدارة المدرسة.",
            "intent": "blocked",
            "entities": {},
        }

    # 1. Classify intent using Gemini
    intent = await gemini.classify_intent(msg)

    # 2. RBAC check
    if not check_rbac(role, intent):
        return {
            "reply": f"عذرًا، ليس لديك صلاحية لهذا الطلب ({intent}). تواصل مع المسؤول.",
            "intent": intent,
            "entities": {},
        }

    # 3. Extract entities
    entities = extract_entities(msg)

    # 4. Execute handler
    handler = INTENT_HANDLERS.get(intent)
    if handler:
        reply = await handler(entities, token, msg)
    elif intent == "greeting":
        reply = f"أهلاً وسهلاً! 👋 أنا مساعد أراك الذكي. كيف يمكنني مساعدتك اليوم؟"
    else:
        reply = "لم أفهم طلبك بوضوح. يمكنني مساعدتك في:\n• حضور وغياب الطلاب\n• الدرجات والتقييمات\n• جدول الحصص\n• تحليل الأداء والطلاب الضعفاء\n• ملخص الفصل أو اليوم\n• الرسوم غير المدفوعة"

    return {"reply": reply, "intent": intent, "entities": entities}
