from contextlib import asynccontextmanager
import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.router import api_router
from backend.container import AppContainer
from backend.infra.config import load_settings
from backend.infra.db import create_engine_and_session, init_db
from backend.infra.errors import APIError
from backend.infra.report_store import ReportStore
from backend.repositories.analysis_repo import AnalysisRepository
from backend.repositories.job_repo import JobRepository
from backend.services.analysis_service import AnalysisService
from backend.services.job_runner import JobRunner


load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")
load_dotenv()
logger = logging.getLogger(__name__)



def create_app() -> FastAPI:
    settings = load_settings()
    if not settings.jwt_secret_key or settings.jwt_secret_key == "change-me":
        raise RuntimeError("JWT_SECRET_KEY must be set to a non-default value.")
    if not settings.auth_username:
        raise RuntimeError("AUTH_USERNAME must be set.")
    if not settings.auth_password_hash:
        raise RuntimeError("AUTH_PASSWORD_HASH must be set.")

    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.report_output_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    db_exists = settings.sqlite_db_path.exists()
    engine, session_factory = create_engine_and_session(settings.sqlite_db_path)
    if not db_exists:
        init_db(engine)

    analysis_repo = AnalysisRepository()
    job_repo = JobRepository()
    report_store = ReportStore(settings.report_output_dir)

    analysis_service = AnalysisService(
        settings=settings,
        session_factory=session_factory,
        analysis_repo=analysis_repo,
        job_repo=job_repo,
        report_store=report_store,
    )

    job_runner = JobRunner()
    job_runner.set_handler(analysis_service.process_job)

    container = AppContainer(
        settings=settings,
        analysis_service=analysis_service,
        job_runner=job_runner,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        _app.state.container.job_runner.start()
        try:
            yield
        finally:
            _app.state.container.job_runner.stop()

    app = FastAPI(title="PEA Agent Backend", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.state.container = container

    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.details,
            },
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(_: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            code = str(detail.get("code") or f"http_{exc.status_code}")
            message = str(detail.get("message") or detail.get("detail") or "Request failed")
            payload_detail = detail.get("detail")
        else:
            code = f"http_{exc.status_code}"
            message = str(detail or "Request failed")
            payload_detail = None
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": message, "detail": payload_detail},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": "Request validation failed",
                "detail": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception):
        logger.exception("Unhandled server error")
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "Internal server error",
                "detail": str(exc),
            },
        )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


app = create_app()
