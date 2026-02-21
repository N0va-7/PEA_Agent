from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.container import AppContainer
from backend.infra.security import decode_token


security_scheme = HTTPBearer(auto_error=True)



def get_container(request: Request) -> AppContainer:
    return request.app.state.container



def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security_scheme),
    container: AppContainer = Depends(get_container),
) -> str:
    payload = decode_token(creds.credentials, container.settings)
    return str(payload["sub"])



def require_auth(_: str = Depends(get_current_user)):
    return True
