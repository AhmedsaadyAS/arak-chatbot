import json, csv, os, sys
sys.path.insert(0, os.getcwd())

with open('data/intents.json', encoding='utf-8') as f:
    data = json.load(f)

rows = []
for intent in data['intents']:
    for pattern in intent['patterns']:
        if pattern.strip():
            rows.append({'text': pattern, 'intent': intent['tag']})

with open('data/dataset.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['text', 'intent'])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated {len(rows)} rows")
for r in rows[:3]:
    print(r)

from pipeline.intent_classifier import IntentClassifier
clf = IntentClassifier()
clf.train()
print("Model retrained!")
