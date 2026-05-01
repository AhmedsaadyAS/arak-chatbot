import requests
import json
import sys

# Ensure UTF-8 output for terminal
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

def test_chat():
    url = "http://localhost:8001/chat"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwidXNlcklkIjoiMSIsInJvbGUiOiJTdXBlciBBZG1pbiIsInVuaXF1ZV9uYW1lIjoiYWRtaW5AYXJhay5jb20iLCJleHAiOjE3Nzc3MTQzNzQsImlzcyI6IkFyYWtBUEkiLCJhdWQiOiJBcmFrRGFzaGJvYXJkIiwiaHR0cDovL3NjaGVtYXMubWljcm9zb2Z0LmNvbS93cy8yMDA4LzA2L2lkZW50aXR5L2NsYWltcy9yb2xlIjoiU3VwZXIgQWRtaW4iLCJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1laWRlbnRpZmllciI6IjEifQ.68ZzCKvwU_Lh53FvIZ0075UWITHd9gu_0i-ferBmogE"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    queries = [
        "من غاب اليوم؟",
        "What are my grades?",
        "Help me",
        "درجاتي في الرياضيات",
        "هل سارة غائبة؟"
    ]
    
    for query in queries:
        payload = {
            "message": query,
            "token": token
        }
        try:
            print(f"\nQuery: {query}")
            response = requests.post(url, json=payload, headers=headers)
            print(f"Response Code: {response.status_code}")
            if response.status_code == 200:
                print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            else:
                print(f"Error Body: {response.text}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    test_chat()
