import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import HTTPException, status

from backend.infra.config import Settings



def hash_password_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()



def verify_username_password(username: str, password: str, settings: Settings) -> bool:
    if not hmac.compare_digest(username, settings.auth_username):
        return False
    if not settings.auth_password_hash:
        return False
    expected = settings.auth_password_hash.lower()
    actual = hash_password_sha256(password).lower()
    return hmac.compare_digest(expected, actual)



def create_access_token(subject: str, settings: Settings) -> Dict[str, str | int]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.jwt_expire_hours * 3600,
    }



def decode_token(token: str, settings: Settings) -> Dict[str, str | int]:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    if "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    return payload
