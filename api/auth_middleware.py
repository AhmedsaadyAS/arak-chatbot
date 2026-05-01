import os
from typing import Dict, Any

from fastapi import HTTPException, Request, status
from jose import JWTError, ExpiredSignatureError, jwt
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-env")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ISSUER = os.getenv("JWT_ISSUER", "")
AUDIENCE = os.getenv("JWT_AUDIENCE", "")


def _extract_bearer_token(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )
    return auth_header.split(" ", 1)[1].strip()


def get_current_user(request: Request) -> Dict[str, Any]:
    token = _extract_bearer_token(request)

    try:
        options = {}
        decode_kwargs: dict = {
            "algorithms": [ALGORITHM],
            "options": options,
        }
        if ISSUER:
            decode_kwargs["issuer"] = ISSUER
        if AUDIENCE:
            decode_kwargs["audience"] = AUDIENCE

        payload = jwt.decode(token, SECRET_KEY, **decode_kwargs)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    # ملاحظة: ندعم أكثر من اسم claim للتوافق مع إعدادات .NET المختلفة
    role = (
        payload.get("role")
        or payload.get("roles")
        or payload.get("http://schemas.microsoft.com/ws/2008/06/identity/claims/role")
    )
    user_id = (
        payload.get("userId")
        or payload.get("user_id")
        or payload.get("id")
        or payload.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/nameidentifier")
        or payload.get("sub")
    )

    if isinstance(role, list):
        role = role[0] if role else None

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        user_id = 0

    if not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing role in token",
        )

    request.state.user = {"role": role, "userId": user_id, "token": token}
    request.state.token = token
    return request.state.user
