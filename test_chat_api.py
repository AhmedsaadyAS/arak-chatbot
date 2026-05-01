#!/usr/bin/env python3
"""
Test the Chatbot API with authentication
"""
import requests
import json
from datetime import datetime, timedelta, timezone
from jose import jwt

# Configuration
CHATBOT_URL = "http://localhost:8001"
JWT_SECRET = "Arak_Development_Only_Key_Change_In_Production_2026"  # From .env
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "ArakAPI"
JWT_AUDIENCE = "ArakDashboard"

# Test messages
TEST_MESSAGES = [
    ("من غاب اليوم", "attendance_query"),
    ("درجات أحمد", "student_grade"),
    ("ما موعد الحصة", "schedule_query"),
    ("السلام عليكم", "help"),
    ("tell me student grades", "student_query"),
]

def generate_test_token(user_role="Super Admin", user_id=1):
    """Generate a valid JWT token for testing"""
    payload = {
        "userId": user_id,
        "role": user_role,
        "email": f"test-{user_role.lower()}@arak.com",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token

def test_health():
    """Test health endpoint"""
    print("=" * 60)
    print("1. Testing Health Endpoint")
    print("=" * 60)
    try:
        response = requests.get(f"{CHATBOT_URL}/health")
        print(f"✓ Status: {response.status_code}")
        print(f"✓ Response: {response.json()}")
        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_chat_endpoint(token, message, expected_intent=None):
    """Test chat endpoint with authentication"""
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"message": message}
    
    try:
        response = requests.post(
            f"{CHATBOT_URL}/chat",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            intent = data.get("intent")
            confidence = data.get("confidence", 0)
            reply = data.get("reply", "No reply")[:60] + "..."
            
            status = "✓"
            if expected_intent and intent != expected_intent:
                status = "~"
            
            print(f"{status} Intent: {intent:20} | Confidence: {confidence:.4f}")
            print(f"  Message: {message}")
            print(f"  Reply: {reply}")
            return True
        else:
            print(f"✗ HTTP {response.status_code}: {response.text[:100]}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_role_based_access(token, role_name):
    """Test role-based access control"""
    print(f"\n{'=' * 60}")
    print(f"Testing as: {role_name}")
    print(f"{'=' * 60}")
    
    passed = 0
    for message, expected_intent in TEST_MESSAGES:
        if test_chat_endpoint(token, message, expected_intent):
            passed += 1
        print()
    
    print(f"Result: {passed}/{len(TEST_MESSAGES)} tests passed")
    return passed == len(TEST_MESSAGES)

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ARAK CHATBOT API TEST SUITE")
    print("=" * 60 + "\n")
    
    # Test 1: Health Check
    if not test_health():
        print("\n✗ Chatbot API is not running!")
        exit(1)
    
    print("\n")
    
    # Test 2: Super Admin Access
    token = generate_test_token(user_role="Super Admin", user_id=1)
    test_role_based_access(token, "Super Admin")
    
    # Test 3: Teacher Access
    print("\n\n")
    token = generate_test_token(user_role="Teacher", user_id=2)
    test_role_based_access(token, "Teacher")
    
    # Test 4: Parent Access
    print("\n\n")
    token = generate_test_token(user_role="Parent", user_id=3)
    test_role_based_access(token, "Parent")
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETED")
    print("=" * 60)
