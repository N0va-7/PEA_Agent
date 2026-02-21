from urllib.parse import parse_qs, urlparse

from fastapi import APIRouter, Depends
from sqlalchemy.engine.url import make_url

from backend.api.deps import get_container, require_auth
from backend.container import AppContainer


router = APIRouter(prefix="/system", tags=["system"], dependencies=[Depends(require_auth)])


def _safe_db_info(database_url: str) -> dict:
    try:
        url = make_url(database_url)
    except Exception:
        return {"driver": "unknown", "display": "invalid_database_url"}

    driver = (url.drivername or "unknown").strip()
    if driver.startswith("sqlite"):
        db_name = str(url.database or "")
        return {
            "driver": driver,
            "host": "local-file",
            "port": None,
            "database": db_name,
            "username": None,
            "has_password": False,
            "display": f"{driver}://local-file/{db_name}",
        }

    return {
        "driver": driver,
        "host": url.host,
        "port": url.port,
        "database": url.database,
        "username": url.username,
        "has_password": bool(url.password),
        "display": f"{driver}://{url.host}:{url.port}/{url.database}",
    }


def _safe_redis_info(redis_url: str, backend: str) -> dict:
    if backend != "redis":
        return {"backend": backend, "enabled": False}

    parsed = urlparse(redis_url or "")
    qs = parse_qs(parsed.query)
    db = 0
    if parsed.path and parsed.path != "/":
        try:
            db = int(parsed.path.lstrip("/"))
        except ValueError:
            db = 0
    elif "db" in qs and qs["db"]:
        try:
            db = int(qs["db"][0])
        except ValueError:
            db = 0

    return {
        "backend": backend,
        "enabled": True,
        "host": parsed.hostname,
        "port": parsed.port,
        "db": db,
        "username": parsed.username,
        "has_password": bool(parsed.password),
        "display": f"redis://{parsed.hostname}:{parsed.port}/{db}",
    }


@router.get("/runtime-info")
def get_runtime_info(container: AppContainer = Depends(get_container)):
    settings = container.settings
    return {
        "database": _safe_db_info(settings.database_url),
        "queue": _safe_redis_info(settings.redis_url, settings.job_queue_backend),
        "model_dir": str(settings.model_dir),
        "upload_dir": str(settings.upload_dir),
        "report_output_dir": str(settings.report_output_dir),
    }

