from fastapi import APIRouter, Depends, status

from backend.api.deps import get_container
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.infra.security import create_access_token, verify_username_password
from backend.schemas.auth import LoginRequest, TokenResponse


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, container: AppContainer = Depends(get_container)):
    if not verify_username_password(payload.username, payload.password, container.settings):
        raise_api_error(status_code=status.HTTP_401_UNAUTHORIZED, code="invalid_credentials", message="Invalid credentials")
    token = create_access_token(payload.username, container.settings)
    return TokenResponse(**token)
