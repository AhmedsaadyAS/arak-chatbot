import json
import csv
import os

def generate_dataset():
    intents_path = 'data/intents.json'
    dataset_path = 'data/dataset.csv'
    
    if not os.path.exists(intents_path):
        print(f"Error: {intents_path} not found.")
        return

    with open(intents_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    rows = []
    
    # Automated Data Augmentation with Entities
    students = ["Ahmed", "Sara", "Youssef", "Layla", "Mohamed", "Zain", "Nour", "Mariam", "أحمد", "سارة", "يوسف", "ليلى", "محمد", "زين", "نور", "مريم"]
    classes = ["Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5", "Grade 6", "الصف الأول", "الصف الثاني", "الصف الثالث", "الصف الرابع"]
    subjects = ["Math", "Science", "English", "Arabic", "History", "الرياضيات", "العلوم", "الانجليزي", "اللغة العربية", "التاريخ"]
    
    for intent in data['intents']:
        tag = intent['tag']
        # Add base patterns
        for pattern in intent['patterns']:
            rows.append([pattern, tag])
            
        # Augment Attendance
        if tag == 'attendance_query':
            for s in students:
                rows.append([f"هل {s} غائب اليوم؟", tag])
                rows.append([f"is {s} absent?", tag])
            for c in classes:
                rows.append([f"غياب {c}", tag])
                rows.append([f"attendance for {c}", tag])
                
        # Augment Grades
        if tag == 'student_grade':
            for s in students:
                for sub in subjects:
                    rows.append([f"درجة {s} في {sub}", tag])
                    rows.append([f"{s} grade in {sub}", tag])
                rows.append([f"درجات {s}", tag])
                
        # Augment Schedule
        if tag == 'schedule_query':
            for c in classes:
                rows.append([f"جدول {c}", tag])
                rows.append([f"schedule for {c}", tag])
            for sub in subjects:
                rows.append([f"متى حصة {sub}؟", tag])
                rows.append([f"when is {sub} class?", tag])

        # Augment Tasks
        if tag == 'task_status':
            for s in students:
                rows.append([f"مهام {s}", tag])
                rows.append([f"tasks for {s}", tag])
            for c in classes:
                rows.append([f"واجبات {c}", tag])
                rows.append([f"homework for {c}", tag])

        # Augment Help/General
        if tag == 'help':
            extra = ["ماذا تفعل؟", "أريد المساعدة", "كيف حالك؟", "how can you help me?", "what are your features?", "chatbot help"]
            for e in extra: rows.append([e, tag])

    # Final count check - ensuring at least 10 per intent
    counts = {}
    for r in rows:
        counts[r[1]] = counts.get(r[1], 0) + 1
        
    for tag, count in counts.items():
        if count < 15:
            # Duplicate existing ones to reach minimum for small classes
            existing = [r for r in rows if r[1] == tag]
            while len([r for r in rows if r[1] == tag]) < 15:
                rows.append(existing[0])

    with open(dataset_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['text', 'intent'])
        writer.writerows(rows)

    print(f"Dataset generated with {len(rows)} examples at {dataset_path}")

if __name__ == "__main__":
    generate_dataset()
