#!/usr/bin/env python3
"""
Simpler test using pre-generated token from backend
"""
import requests
from datetime import datetime, timedelta, timezone
from jose import jwt

CHATBOT_URL = "http://localhost:8001"

# Use exact credentials from .env
JWT_SECRET = "Arak_Development_Only_Key_Change_In_Production_2026"
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "ArakAPI"
JWT_AUDIENCE = "ArakDashboard"

# Generate token
payload = {
    "userId": 1,
    "role": "Super Admin",
    "iss": JWT_ISSUER,
    "aud": JWT_AUDIENCE,
    "exp": datetime.now(timezone.utc) + timedelta(hours=1)
}

try:
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    print(f"[OK] Token generated: {token[:50]}...")
    
    # Test the endpoint
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test with Arabic message
    response = requests.post(
        f"{CHATBOT_URL}/chat",
        json={"message": "من غاب اليوم"},
        headers=headers
    )
    
    print(f"\nResponse Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
except Exception as e:
    print(f"[ERROR] Error: {e}")
    import traceback
    traceback.print_exc()
