from jose import jwt
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "Arak_Development_Only_Key_Change_In_Production_2026")
ALGORITHM = "HS256"

def generate_token():
    payload = {
        "sub": "1",
        "userId": "1",
        "role": "Super Admin",
        "unique_name": "admin@arak.com",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24),
        "iss": "ArakAPI",
        "aud": "ArakDashboard"
    }
    
    # Add the Microsoft role claim just in case
    payload["http://schemas.microsoft.com/ws/2008/06/identity/claims/role"] = "Super Admin"
    payload["http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier"] = "1"
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    print(token)

if __name__ == "__main__":
    generate_token()
