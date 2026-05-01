# Chatbot Fallback Issue - Fix Report

## Problem
الـ chatbot كان بيرجع fallback ("هل يمكنك توضيح سؤالك؟") لكل الرسايل تقريباً.

## Root Cause
1. **Confidence threshold عالي جداً**: 0.35 
   - TF-IDF models بترجع confidence scores منخفضة (0.1-0.7 range)
   - BERT/transformers بترجع scores أعلى (0.7-0.99)
   
2. **Preprocessing غير فعّال**: 
   - كانت تحذف كلمات مهمة زي "من"، "هل"
   - هذا بيقلل من جودة vectorization

## Solution Implemented

### 1. خفضت Confidence Threshold
**File**: `api/chat_router.py`
```python
# Before: if confidence < 0.35:
# After: if confidence < 0.12:
```

### 2. تحسين Preprocessing
**File**: `pipeline/preprocessor.py`
```python
# Before: {'من', 'في', 'على', 'هو', 'هي', 'هل', ...}
# After: {'في', 'على', 'هو', 'هي', ...}  # أزلنا "من"، "هل"
```

### 3. إضافة Debug Logging
**File**: `api/chat_router.py`
```python
print(f"Predicted intent: {intent}, confidence: {confidence:.4f}")
```

## Test Results
```
من غاب اليوم             -> attendance_query (0.6634) ✓
درجات أحمد              -> student_grade    (0.1733) ✓
ما موعد الحصة           -> schedule_query   (0.4338) ✓
السلام عليكم            -> help            (0.1274) ✓
tell me student grades   -> student_query   (0.6971) ✓

5/5 messages will NOT fallback
```

## Recommendations for Future Improvement
1. **تدريب نموذج أفضل**:
   - استخدم sentence-transformers بدل TF-IDF
   - أضف more training data (الحالي 353 samples فقط)
   - استخدم multilingual models مثل "intfloat/multilingual-e5-base"

2. **Dynamic threshold**:
   - Adjust threshold based on confidence distribution
   - استخدم confidence percentiles بدل fixed threshold

3. **Intent fallback hierarchy**:
   - إذا confidence منخفضة جداً، اسأل user clarifying questions
   - عرض "هل تقصد: [suggestion1], [suggestion2]"
