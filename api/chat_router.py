from fastapi import APIRouter, Depends
from pydantic import BaseModel
from pipeline.intent_classifier import IntentClassifier
from api.arak_client import ArakClient
from api.auth_middleware import get_current_user
import json, re, random
from typing import Dict, Any, Optional

router = APIRouter()
classifier = IntentClassifier()
arak_client = ArakClient()

with open("data/intents.json", "r", encoding="utf-8") as f:
    intents_data = json.load(f)

class ChatRequest(BaseModel):
    message: str
    token: Optional[str] = None

def extract_entities(text: str) -> Dict[str, Any]:
    entities = {}
    lowered = text.lower()
    
    # التقاط رقم الطالب
    s_match = re.search(r"(student|طالب|id)[^\d]{0,10}(\d+)", lowered)
    if s_match: entities["studentId"] = int(s_match.group(2))
    
    # التقاط رقم الفصل أو الاسم
    c_match = re.search(r"(class|الفصل|فصل|صف|grade)[^\d]{0,10}(\d+[-a-z]?)", lowered)
    if c_match:
        val = c_match.group(2)
        if val.isdigit(): entities["classId"] = int(val)
        else: entities["classLookup"] = val
    
    return entities

async def _resolve_class_id(lookup: str, token: str):
    classes = await arak_client.get_classes(token=token)
    if isinstance(classes, list):
        for c in classes:
            if lookup in str(c.get("name", "")).lower() or lookup in str(c.get("grade", "")).lower():
                return c.get("id")
    return None

@router.post("/chat")
async def chat(request: ChatRequest, user: Dict[str, Any] = Depends(get_current_user)):
    msg = request.message.lower()
    token = user.get("token", "")
    
    # 1. Hard Overrides (Priority Over Model)
    if any(k in msg for k in ["غياب", "حضور", "attendance"]):
        intent = "attendance_query"
    elif any(k in msg for k in ["درجة", "نتيجة", "grade", "score"]):
        intent = "student_grade"
    elif any(k in msg for k in ["جدول", "حصص", "schedule"]):
        intent = "schedule_query"
    else:
        intent, _ = classifier.predict(request.message)

    entities = extract_entities(request.message)
    reply = ""

    # 2. Logic execution
    if intent == "attendance_query":
        cid = entities.get("classId")
        if not cid and entities.get("classLookup"):
            cid = await _resolve_class_id(entities["classLookup"], token)
        
        if cid:
            data = await arak_client.get_attendance_by_class(cid, token)
            reply = arak_client.format_attendance(data)
        else:
            reply = "من فضلك حدد رقم الفصل (مثال: غياب الفصل 1)."

    elif intent == "student_grade":
        sid = entities.get("studentId")
        if sid:
            data = await arak_client.get_student_grades(sid, token)
            reply = arak_client.format_grades(data)
        else:
            reply = "من فضلك حدد رقم الطالب (مثال: درجات الطالب 5)."
            
    else:
        reply = "أنا هنا للمساعدة. كيف يمكنني مساعدتك اليوم؟"

    return {"reply": reply, "intent": intent, "entities": entities}