import threading
import time

from fastapi import APIRouter, Depends, status
from fastapi import Request

from backend.api.deps import get_container
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.infra.security import create_access_token, verify_username_password
from backend.schemas.auth import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])
_FAILED_LOGINS: dict[str, list[float]] = {}
_FAILED_LOGINS_LOCK = threading.Lock()


def _client_key(request: Request, username: str) -> str:
    host = request.client.host if request.client and request.client.host else "unknown"
    return f"{host}:{username}"


def _trim_timestamps(raw: list[float], now_ts: float, window_seconds: int) -> list[float]:
    cutoff = now_ts - max(1, window_seconds)
    return [ts for ts in raw if ts >= cutoff]


def _is_rate_limited(key: str, now_ts: float, *, max_attempts: int, window_seconds: int) -> bool:
    with _FAILED_LOGINS_LOCK:
        current = _trim_timestamps(_FAILED_LOGINS.get(key, []), now_ts, window_seconds)
        _FAILED_LOGINS[key] = current
        return len(current) >= max_attempts


def _record_failed_attempt(key: str, now_ts: float, *, window_seconds: int):
    with _FAILED_LOGINS_LOCK:
        current = _trim_timestamps(_FAILED_LOGINS.get(key, []), now_ts, window_seconds)
        current.append(now_ts)
        _FAILED_LOGINS[key] = current


def _clear_failed_attempts(key: str):
    with _FAILED_LOGINS_LOCK:
        _FAILED_LOGINS.pop(key, None)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, container: AppContainer = Depends(get_container)):
    now_ts = time.time()
    key = _client_key(request, payload.username)
    if _is_rate_limited(
        key,
        now_ts,
        max_attempts=container.settings.login_rate_max_attempts,
        window_seconds=container.settings.login_rate_window_seconds,
    ):
        raise_api_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="too_many_login_attempts",
            message="Too many failed login attempts. Please retry later.",
        )

    if not verify_username_password(payload.username, payload.password, container.settings):
        _record_failed_attempt(
            key,
            now_ts,
            window_seconds=container.settings.login_rate_window_seconds,
        )
        raise_api_error(status_code=status.HTTP_401_UNAUTHORIZED, code="invalid_credentials", message="Invalid credentials")

    _clear_failed_attempts(key)
    token = create_access_token(payload.username, container.settings)
    return TokenResponse(**token)
