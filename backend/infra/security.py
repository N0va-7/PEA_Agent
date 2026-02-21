import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Dict

import jwt
from fastapi import HTTPException, status

from backend.infra.config import Settings



def hash_password_sha256(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def hash_password_pbkdf2(password: str, *, iterations: int = 260000) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def _verify_password(password: str, expected_hash: str) -> bool:
    expected = (expected_hash or "").strip()
    if not expected:
        return False

    # Backward compatibility for existing deployments.
    if expected.startswith("pbkdf2_sha256$"):
        try:
            _, iter_raw, salt, digest_hex = expected.split("$", 3)
            iterations = int(iter_raw)
        except ValueError:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
        return hmac.compare_digest(digest.lower(), digest_hex.lower())

    actual = hash_password_sha256(password).lower()
    return hmac.compare_digest(actual, expected.lower())



def verify_username_password(username: str, password: str, settings: Settings) -> bool:
    if not hmac.compare_digest(username, settings.auth_username):
        return False
    if not settings.auth_password_hash:
        return False
    return _verify_password(password, settings.auth_password_hash)



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
