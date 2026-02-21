from contextlib import asynccontextmanager
import logging
from pathlib import Path

from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text

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


def _warn_schema_drift(engine):
    try:
        inspector = inspect(engine)
        if not inspector.has_table("alembic_version"):
            logger.info("alembic_version table not found; schema drift check skipped.")
            return

        with engine.connect() as conn:
            version_rows = list(conn.execute(text("SELECT version_num FROM alembic_version")))
        db_versions = {str(row[0]) for row in version_rows if row and row[0]}

        alembic_cfg = AlembicConfig()
        alembic_cfg.set_main_option("script_location", str(Path(__file__).resolve().parent / "alembic"))
        script = ScriptDirectory.from_config(alembic_cfg)
        head_versions = set(script.get_heads())
        if db_versions and db_versions.isdisjoint(head_versions):
            logger.warning(
                "Database schema may be outdated. db_versions=%s, code_heads=%s",
                sorted(db_versions),
                sorted(head_versions),
            )
    except Exception:
        logger.exception("Failed to check alembic schema drift.")



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

    is_sqlite = settings.database_url.strip().lower().startswith("sqlite:")
    db_exists = settings.sqlite_db_path.exists() if is_sqlite else False
    engine, session_factory = create_engine_and_session(
        settings.sqlite_db_path if is_sqlite else None,
        settings.database_url,
    )
    if (is_sqlite and not db_exists) or (not is_sqlite):
        init_db(engine)
    _warn_schema_drift(engine)

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

    job_runner = JobRunner(
        backend=settings.job_queue_backend,
        redis_url=settings.redis_url,
        queue_name=settings.redis_queue_name,
    )
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
                "detail": str(exc) if settings.expose_internal_error_details else None,
            },
        )

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    return app


app = create_app()
