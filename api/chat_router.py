from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from api.arak_client import ArakClient
from api.ai_service import AIService, ModelConfig
from api.auth_middleware import get_current_user
import re
from datetime import date
from typing import Dict, Any, Optional, List


router = APIRouter()
arak_client = ArakClient()
ai = AIService()


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


PARENT_SAFE_MESSAGES = {
    "attendance_missing_child": "لم أتمكن من تحديد بيانات ابنك حاليا.",
    "attendance_missing_class": "لم أتمكن من تحديد فصل ابنك حاليا.",
    "grade_missing_child": "لم أتمكن من تحديد بيانات ابنك حاليا.",
    "fee_missing_child": "لم أتمكن من تحديد بيانات ابنك حاليا.",
    "schedule_missing_class": "لم أتمكن من تحديد فصل ابنك حاليا.",
}



class ChatRequest(BaseModel):
    message: str
    token: Optional[str] = None
    model_config_data: Optional[dict] = None



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


def _first_value(data: Any, *keys: str):
    if not isinstance(data, dict):
        return None

    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _norm(value: Any) -> str:
    return str(value).strip().casefold()


def _matches_exact(candidate: Any, value: Any) -> bool:
    if candidate in (None, "") or value in (None, ""):
        return False
    return _norm(candidate) == _norm(value)


def _parent_intent_override(message: str) -> Optional[str]:
    msg = message.casefold().strip()

    if any(w in msg for w in ["غياب", "حضور", "غاب", "متغيب", "absent", "attendance"]):
        return "attendance_query"
    if any(w in msg for w in ["جدول", "حصص", "مواعيد", "schedule", "timetable"]):
        return "schedule_query"
    if any(w in msg for w in ["درجة", "درجات", "تقييم", "نتيجة", "علامة", "grade", "grades"]):
        return "student_grade"
    if any(w in msg for w in ["رسوم", "مصروفات", "مدفوعات", "فواتير", "fees"]):
        return "fee_status"
    if any(w in msg for w in ["فعالية", "فعاليات", "أحداث", "نشاط", "event"]):
        return "event_query"

    return None


async def _resolve_parent_class_id(
    parent_profile: Dict[str, Any],
    matched_student: Dict[str, Any],
    token: str,
) -> Optional[int]:
    existing_class_id = _first_value(matched_student, "classId", "ClassId")
    if existing_class_id not in (None, ""):
        try:
            return int(existing_class_id)
        except (TypeError, ValueError):
            return existing_class_id

    parent_id = _first_value(parent_profile, "id", "parentId")
    if parent_id in (None, ""):
        return None

    linked_students = await arak_client.get_students_by_parent_id(parent_id, token)
    if not isinstance(linked_students, list) or not linked_students:
        return None

    matched_student_id = _first_value(matched_student, "id", "Id")
    lookup_values = [
        _first_value(matched_student, "class_number", "classNumber"),
        _first_value(matched_student, "grade", "Grade"),
        _first_value(matched_student, "className", "ClassName"),
        _first_value(matched_student, "class_name", "className"),
    ]

    def _linked_class_id(student: Dict[str, Any]):
        class_id = _first_value(student, "classId", "ClassId")
        if class_id in (None, ""):
            return None
        try:
            return int(class_id)
        except (TypeError, ValueError):
            return class_id

    for student in linked_students:
        if _matches_exact(_first_value(student, "id", "Id"), matched_student_id):
            class_id = _linked_class_id(student)
            if class_id is not None:
                return class_id

    for value in lookup_values:
        if value in (None, ""):
            continue
        for student in linked_students:
            if any(
                _matches_exact(value, candidate)
                for candidate in (
                    _first_value(student, "classId", "ClassId"),
                    _first_value(student, "grade", "Grade"),
                    _first_value(student, "className", "ClassName"),
                )
            ):
                class_id = _linked_class_id(student)
                if class_id is not None:
                    return class_id

    for value in lookup_values:
        if value in (None, ""):
            continue
        for student in linked_students:
            class_name = _first_value(student, "className", "ClassName")
            if class_name and _norm(value) in _norm(class_name):
                class_id = _linked_class_id(student)
                if class_id is not None:
                    return class_id

    return None


async def _resolve_parent_student_context(message: str, token: str) -> Dict[str, Any]:
    parent_profile = await arak_client.get_parent_profile(token)
    students = parent_profile.get("students", []) if isinstance(parent_profile, dict) else []

    if not isinstance(students, list) or not students:
        return {}

    parent_id = _first_value(parent_profile, "id", "parentId")
    linked_students = []
    if parent_id not in (None, ""):
        fetched_students = await arak_client.get_students_by_parent_id(parent_id, token)
        if isinstance(fetched_students, list):
            linked_students = fetched_students

    msg_lower = message.lower().strip()
    matched_student = None

    for student in students:
        candidate_names = [
            str(student.get("name", "")).strip(),
            str(student.get("fullName", "")).strip(),
            str(student.get("studentName", "")).strip(),
        ]

        for candidate in candidate_names:
            if not candidate:
                continue

            candidate_lower = candidate.lower()
            if candidate_lower and candidate_lower in msg_lower:
                matched_student = student
                break

            for part in candidate_lower.split():
                if len(part) >= 3 and part in msg_lower:
                    matched_student = student
                    break

            if matched_student:
                break

        if matched_student:
            break

    if not matched_student:
        matched_student = students[0]

    class_id = await _resolve_parent_class_id(parent_profile, matched_student, token)
    class_number = _first_value(matched_student, "class_number", "classNumber")
    class_name = _first_value(matched_student, "className", "class_name", "ClassName")

    linked_student_record = None
    matched_student_id = _first_value(matched_student, "id", "Id")
    for student in linked_students:
        if _matches_exact(_first_value(student, "id", "Id"), matched_student_id):
            linked_student_record = student
            break

    if linked_student_record is not None and class_id is None:
        class_id = _first_value(linked_student_record, "classId", "ClassId")
        if class_id not in (None, ""):
            try:
                class_id = int(class_id)
            except (TypeError, ValueError):
                pass

    return {
        "studentId": matched_student.get("id"),
        "classId": class_id,
        "classNumber": class_number,
        "className": class_name,
        "studentName": matched_student.get("name")
            or matched_student.get("fullName")
            or matched_student.get("studentName"),
    }



# ── Intent Handlers ─────────────────────────────────────────────────


async def handle_attendance_query(
    entities: Dict,
    token: str,
    message: str,
    mc: Optional[ModelConfig] = None,
    role: Optional[str] = None,
) -> str:
    if role == "Parent":
        sid = entities.get("studentId")
        if sid:
            data = await arak_client.get_student_attendance(sid, token)
            if isinstance(data, dict) and "error" in data:
                return PARENT_SAFE_MESSAGES["attendance_missing_child"]
            return await ai.format_response("attendance_query", data, message, config=mc)
        return PARENT_SAFE_MESSAGES["attendance_missing_child"]

    cid = entities.get("classId")
    if not cid and entities.get("classLookup"):
        cid = await _resolve_class_id(entities["classLookup"], token)
    if cid:
        data = await arak_client.get_attendance_by_class(cid, token)
        if isinstance(data, dict) and "error" in data:
            return "لم أتمكن من جلب بيانات الحضور. تأكد من رقم الفصل."
        return await ai.format_response("attendance_query", data, message, config=mc)
    return "من فضلك حدد رقم الفصل (مثال: غياب الفصل 1)."
async def handle_student_grade(
    entities: Dict,
    token: str,
    message: str,
    mc: Optional[ModelConfig] = None,
    role: Optional[str] = None,
) -> str:
    sid = entities.get("studentId")

    if role == "Parent" and not sid:
        return PARENT_SAFE_MESSAGES["grade_missing_child"]

    if sid:
        data = await arak_client.get_student_grades(sid, token)
        if isinstance(data, list) and data:
            return await ai.format_response("student_grade", data, message, config=mc)
        return "لا توجد درجات مسجلة لهذا الطالب."

    return PARENT_SAFE_MESSAGES["grade_missing_child"]
async def handle_schedule_query(
    entities: Dict,
    token: str,
    message: str,
    mc: Optional[ModelConfig] = None,
    role: Optional[str] = None,
) -> str:
    if role == "Parent":
        cid = entities.get("classId")
        if cid:
            data = await arak_client.get_schedules_by_class(cid, token)
            if isinstance(data, list) and data:
                return await ai.format_response("schedule_query", data, message, config=mc)
            return "لا يوجد جدول حصص متاح حاليا لابنك."
        return PARENT_SAFE_MESSAGES["schedule_missing_class"]

    cid = entities.get("classId")
    if not cid and entities.get("classLookup"):
        cid = await _resolve_class_id(entities["classLookup"], token)
    if cid:
        data = await arak_client.get_schedules_by_class(cid, token)
        if isinstance(data, list) and data:
            return await ai.format_response("schedule_query", data, message, config=mc)
        return "لا يوجد جدول حصص لهذا الفصل."
    return "من فضلك حدد رقم الفصل (مثال: جدول الفصل 1)."
async def handle_top_absentees(token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    """Find students with the most absences."""
    classes = await arak_client.get_classes(token=token)
    if not isinstance(classes, list):
        return "لم أتمكن من جلب بيانات الفصول."

    absence_counts = {}
    for cls in classes[:10]:
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
    return await ai.analyze_data(
        "حلل بيانات أكثر الطلاب غيابًا وقدم توصيات لتحسين الحضور:",
        {"top_absentees": top_5},
        config=mc,
    )



async def handle_weak_students(entities: Dict, token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
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
    return await ai.analyze_data(
        "حلل بيانات الطلاب ذوي الأداء الضعيف (أقل من 50 درجة) وقدم توصيات:",
        {"weak_students": weak[:20], "total_count": len(weak)},
        config=mc,
    )



async def handle_class_summary(entities: Dict, token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    """Comprehensive class summary: attendance + grades + tasks."""
    cid = entities.get("classId")
    if not cid and entities.get("classLookup"):
        cid = await _resolve_class_id(entities["classLookup"], token)
    if not cid:
        return "من فضلك حدد رقم الفصل (مثال: ملخص الفصل 1)."

    attendance = await arak_client.get_attendance_by_class(cid, token)
    evaluations = await arak_client.get_all_evaluations(token)
    tasks = await arak_client.get_all_tasks(token)

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

    return await ai.analyze_data(
        f"قدم ملخصًا شاملًا للفصل رقم {cid} يشمل: الحضور، الدرجات، المهام، وتوصيات لتحسين الأداء:",
        summary_data,
        config=mc,
    )



async def handle_unpaid_fees(token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
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

    return await ai.analyze_data(
        "حلل بيانات الرسوم غير المدفوعة وقدم ملخصًا:",
        {"unpaid_fees": unpaid[:20], "total_unpaid": len(unpaid)},
        config=mc,
    )



async def handle_daily_summary(token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    """Today's summary: attendance + events."""
    today = date.today().isoformat()

    classes = await arak_client.get_classes(token=token)
    events = await arak_client.get_events(token)

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

    return await ai.analyze_data(
        f"قدم ملخص اليوم ({today}) للمدرسة يشمل: إجمالي الحضور والغياب لكل فصل، والأحداث المقررة:",
        summary_data,
        config=mc,
    )



async def handle_fee_status(
    entities: Dict,
    token: str,
    message: str,
    mc: Optional[ModelConfig] = None,
    role: Optional[str] = None,
) -> str:
    sid = entities.get("studentId")
    fees = await arak_client.get_all_fees(token)

    if not isinstance(fees, list):
        return "لم أتمكن من جلب بيانات الرسوم."

    if role == "Parent" and not sid:
        return PARENT_SAFE_MESSAGES["fee_missing_child"]

    if sid:
        student_fees = [f for f in fees if str(f.get("studentId")) == str(sid)]
        if student_fees:
            return await ai.format_response("fee_status", student_fees, message, config=mc)
        return "لا توجد رسوم مسجلة لهذا الطالب."

    return PARENT_SAFE_MESSAGES["fee_missing_child"]
async def handle_task_status(entities: Dict, token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    tasks = await arak_client.get_all_tasks(token)
    if not isinstance(tasks, list):
        return "لم أتمكن من جلب المهام."
    cid = entities.get("classId")
    if cid:
        tasks = [t for t in tasks if str(t.get("classId")) == str(cid)]
    if tasks:
        return await ai.format_response("task_status", tasks[:15], message, config=mc)
    return "لا توجد مهام حاليًا."



async def handle_event_query(token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    events = await arak_client.get_events(token)
    if isinstance(events, list) and events:
        return await ai.format_response("event_query", events[:10], message, config=mc)
    return "لا توجد أحداث مسجلة حاليًا."



async def handle_class_info(entities: Dict, token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    classes = await arak_client.get_classes(token=token)
    if isinstance(classes, list) and classes:
        cid = entities.get("classId")
        if cid:
            cls = next((c for c in classes if c.get("id") == cid), None)
            if cls:
                return await ai.format_response("class_info", cls, message, config=mc)
            return f"الفصل رقم {cid} غير موجود."
        return await ai.format_response("class_info", classes, message, config=mc)
    return "لم أتمكن من جلب بيانات الفصول."



async def handle_teacher_query(token: str, message: str, mc: Optional[ModelConfig] = None) -> str:
    teachers = await arak_client.get_all_teachers(token)
    if isinstance(teachers, list) and teachers:
        return await ai.format_response("teacher_query", teachers[:15], message, config=mc)
    return "لم أتمكن من جلب بيانات المعلمين."



# ── Intent → Handler mapping ────────────────────────────────────────
# All handlers accept (entities, token, message, mc, role)


INTENT_HANDLERS = {
    "attendance_query": lambda e, t, m, mc, r: handle_attendance_query(e, t, m, mc, r),
    "student_grade":    lambda e, t, m, mc, r: handle_student_grade(e, t, m, mc, r),
    "schedule_query":   lambda e, t, m, mc, r: handle_schedule_query(e, t, m, mc, r),
    "top_absentees":    lambda e, t, m, mc, r: handle_top_absentees(t, m, mc),
    "weak_students":    lambda e, t, m, mc, r: handle_weak_students(e, t, m, mc),
    "class_summary":    lambda e, t, m, mc, r: handle_class_summary(e, t, m, mc),
    "unpaid_fees":      lambda e, t, m, mc, r: handle_unpaid_fees(t, m, mc),
    "daily_summary":    lambda e, t, m, mc, r: handle_daily_summary(t, m, mc),
    "fee_status":       lambda e, t, m, mc, r: handle_fee_status(e, t, m, mc, r),
    "task_status":      lambda e, t, m, mc, r: handle_task_status(e, t, m, mc),
    "event_query":      lambda e, t, m, mc, r: handle_event_query(t, m, mc),
    "class_info":       lambda e, t, m, mc, r: handle_class_info(e, t, m, mc),
    "teacher_query":    lambda e, t, m, mc, r: handle_teacher_query(t, m, mc),
}



@router.post("/chat")
async def chat(request: ChatRequest, user: Dict[str, Any] = Depends(get_current_user)):
    msg = request.message
    token = user.get("token", "")
    role = user.get("role", "")

    # Build per-request ModelConfig
    mc = ModelConfig(**(request.model_config_data or {}))

    # Block Student role
    if role in BLOCKED_ROLES:
        return {
            "reply": "عذرًا، هذه الخدمة غير متاحة للطلاب حاليًا. يرجى التواصل مع إدارة المدرسة.",
            "intent": "blocked",
            "entities": {},
        }

    # 1. Classify intent using parent override first, then AI fallback
    if role == "Parent":
        parent_override = _parent_intent_override(msg)
        if parent_override:
            intent = parent_override
            layer = "parent_override"
        else:
            intent, layer = await ai.classify_intent(msg, config=mc)
    else:
        intent, layer = await ai.classify_intent(msg, config=mc)

    # 2. RBAC check
    if not check_rbac(role, intent):
        return {
            "reply": f"عذرًا، ليس لديك صلاحية لهذا الطلب ({intent}). تواصل مع المسؤول.",
            "intent": intent,
            "entities": {},
        }

    # 3. Extract entities
    entities = extract_entities(msg)

    if role == "Parent":
        parent_context = await _resolve_parent_student_context(msg, token)
        if parent_context.get("studentId") and not entities.get("studentId"):
            entities["studentId"] = parent_context["studentId"]
        if parent_context.get("classId") and not entities.get("classId"):
            entities["classId"] = parent_context["classId"]
        if parent_context.get("classNumber") and not entities.get("classNumber"):
            entities["classNumber"] = parent_context["classNumber"]
        if parent_context.get("className") and not entities.get("className"):
            entities["className"] = parent_context["className"]
        if parent_context.get("studentName"):
            entities["studentName"] = parent_context["studentName"]

    # 4. Execute handler
    handler = INTENT_HANDLERS.get(intent)
    if handler:
        reply = await handler(entities, token, msg, mc, role)
    elif intent == "greeting":
        reply = "أهلاً وسهلاً! 👋 أنا مساعد أراك الذكي. كيف يمكنني مساعدتك اليوم؟"
    else:
        reply = "لم أفهم طلبك بوضوح. يمكنني مساعدتك في:\n• حضور وغياب الطلاب\n• الدرجات والتقييمات\n• جدول الحصص\n• تحليل الأداء والطلاب الضعفاء\n• ملخص الفصل أو اليوم\n• الرسوم غير المدفوعة"

    return {"reply": reply, "intent": intent, "entities": entities}


@router.get("/chat/layers")
async def get_active_layers():
    """Return the default layer configuration for the dashboard settings panel."""
    default_mc = ModelConfig()
    return {
        "layers": ai.get_active_layers(default_mc),
        "defaults": default_mc.model_dump(),
    }
