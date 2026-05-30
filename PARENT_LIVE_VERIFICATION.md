# Parent Mode Live Verification

Date: 2026-05-30

## Setup
- Backend: `http://localhost:5000/api`
- Chatbot: `http://localhost:8001/chat`
- Token source: live login for `parent1@arak.com` / `Parent@123`
- Role: `Parent`

## Login Result
- Login status: `200 OK`
- Token: valid Bearer JWT
- Parent profile resolved from backend login

## Live Test Results

| Message | Expected Intent | Actual Intent | Entities | Reply | Result |
|---|---|---|---|---|---|
| `ما هو غياب ابني` | `attendance_query` | `attendance_query` | `studentId=1`, `classId=1`, `classNumber=1`, `className="Grade 4-A"`, `studentName="Alice Parent"` | Attendance report returned successfully | PASS |
| `ما هو جدول ابني` | `schedule_query` | `schedule_query` | `studentId=1`, `classId=1`, `classNumber=1`, `className="Grade 4-A"`, `studentName="Alice Parent"` | Schedule returned successfully | PASS |
| `ما هي درجات ابني` | `student_grade` | `student_grade` | `studentId=1`, `classId=1`, `classNumber=1`, `className="Grade 4-A"`, `studentName="Alice Parent"` | `لا توجد درجات مسجلة لهذا الطالب.` | PASS |
| `ما هي رسوم ابني` | `fee_status` | `fee_status` | `studentId=1`, `classId=1`, `classNumber=1`, `className="Grade 4-A"`, `studentName="Alice Parent"` | `لم أتمكن من جلب بيانات الرسوم.` | FAIL |
| `هل توجد فعاليات قادمة` | `event_query` | `event_query` | `studentId=1`, `classId=1`, `classNumber=1`, `className="Grade 4-A"`, `studentName="Alice Parent"` | `لا توجد أحداث مسجلة حاليًا.` | PASS |

## Summary
- Passed: 4/5
- Failed: 1/5

## Notes
- Parent intent override is working in live mode for attendance, schedule, grades, and events.
- Parent child context resolution is working. The chatbot injects `studentId` and `classId` without asking for IDs.
- The fees query fails live because the backend `FeesController` is restricted to `Super Admin, Admin, Fees Admin`, so the Parent token cannot retrieve fees data from the backend.
- Admin and Teacher behavior were not changed or retested in this live check.
