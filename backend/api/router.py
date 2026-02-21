from fastapi import APIRouter

from backend.api.routes.analyses import router as analyses_router
from backend.api.routes.auth import router as auth_router
from backend.api.routes.jobs import router as jobs_router
from backend.api.routes.reports import router as reports_router


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(analyses_router)
api_router.include_router(jobs_router)
api_router.include_router(reports_router)
