from fastapi import APIRouter

from backend.api.routes.analyses import router as analyses_router
from backend.api.routes.auth import router as auth_router
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.reports import router as reports_router
from backend.api.routes.system import router as system_router
from backend.api.routes.url_checks import router as url_checks_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(analyses_router)
api_router.include_router(jobs_router)
api_router.include_router(reports_router)
api_router.include_router(system_router)
api_router.include_router(url_checks_router)
