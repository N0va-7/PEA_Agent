import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime"
DEFAULT_MODEL_DIR = PROJECT_ROOT / "ml" / "artifacts"


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_llm_base_url(url: str) -> str:
    stripped = (url or "").strip().rstrip("/")
    # Users often provide full endpoint URLs; ChatOpenAI expects a base URL.
    suffixes = ["/chat/completions", "/v1/chat/completions"]
    for suffix in suffixes:
        if stripped.endswith(suffix):
            return stripped[: -len(suffix)] or "https://api.openai.com/v1"
    return stripped or "https://api.openai.com/v1"


def _parse_csv_list(raw: str | None, default: list[str]) -> list[str]:
    if raw is None:
        return default
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or default


def _normalize_database_url(url: str | None, sqlite_db_path: Path) -> str:
    raw = (url or "").strip()
    if not raw:
        return f"sqlite:///{sqlite_db_path}"
    if raw.startswith("mysql://"):
        return "mysql+pymysql://" + raw[len("mysql://") :]
    return raw


@dataclass(frozen=True)
class Settings:
    database_url: str
    sqlite_db_path: Path
    report_output_dir: Path
    upload_dir: Path
    model_dir: Path

    llm_api_key: str
    llm_base_url: str
    llm_model_id: str

    vt_api_key: str
    vt_base_url: str
    vt_enabled: bool
    vt_public_mode: bool
    vt_cache_ttl_hours: int
    vt_min_interval_seconds: int
    vt_daily_budget: int
    vt_timeout_seconds: int

    attachment_sandbox_base_url: str
    attachment_sandbox_source_id: str
    attachment_sandbox_timeout_seconds: int
    attachment_sandbox_poll_interval_seconds: int

    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_hours: int

    cors_allow_origins: list[str]

    auth_username: str
    auth_password_hash: str
    job_queue_backend: str
    redis_url: str
    redis_queue_name: str
    upload_retention_hours: int
    login_rate_max_attempts: int
    login_rate_window_seconds: int
    expose_internal_error_details: bool



def load_settings() -> Settings:
    sqlite_db_path = Path(os.getenv("SQLITE_DB_PATH", str(DEFAULT_RUNTIME_DIR / "db" / "analysis.db"))).expanduser()
    report_output_dir = Path(os.getenv("REPORT_OUTPUT_DIR", str(DEFAULT_RUNTIME_DIR / "reports"))).expanduser()
    upload_dir = Path(os.getenv("UPLOAD_DIR", str(DEFAULT_RUNTIME_DIR / "uploads"))).expanduser()
    model_dir = Path(os.getenv("MODEL_DIR", str(DEFAULT_MODEL_DIR))).expanduser()
    database_url = _normalize_database_url(os.getenv("DATABASE_URL"), sqlite_db_path)

    return Settings(
        database_url=database_url,
        sqlite_db_path=sqlite_db_path,
        report_output_dir=report_output_dir,
        upload_dir=upload_dir,
        model_dir=model_dir,
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=_normalize_llm_base_url(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")),
        llm_model_id=os.getenv("LLM_MODEL_ID", "gpt-4o-mini"),
        vt_api_key=os.getenv("VT_API_KEY", ""),
        vt_base_url=(os.getenv("VT_BASE_URL", "https://www.virustotal.com/api/v3").strip() or "https://www.virustotal.com/api/v3"),
        vt_enabled=_bool_env("VT_ENABLED", True),
        vt_public_mode=_bool_env("VT_PUBLIC_MODE", True),
        vt_cache_ttl_hours=max(1, _int_env("VT_CACHE_TTL_HOURS", 24)),
        vt_min_interval_seconds=max(1, _int_env("VT_MIN_INTERVAL_SECONDS", 15)),
        vt_daily_budget=max(1, _int_env("VT_DAILY_BUDGET", 500)),
        vt_timeout_seconds=max(1, _int_env("VT_TIMEOUT_SECONDS", 20)),
        attachment_sandbox_base_url=(os.getenv("ATTACHMENT_SANDBOX_BASE_URL", "").strip().rstrip("/")),
        attachment_sandbox_source_id=(os.getenv("ATTACHMENT_SANDBOX_SOURCE_ID", "pea-agent").strip() or "pea-agent"),
        attachment_sandbox_timeout_seconds=max(5, _int_env("ATTACHMENT_SANDBOX_TIMEOUT_SECONDS", 45)),
        attachment_sandbox_poll_interval_seconds=max(1, _int_env("ATTACHMENT_SANDBOX_POLL_INTERVAL_SECONDS", 2)),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_expire_hours=_int_env("JWT_EXPIRE_HOURS", 8),
        cors_allow_origins=_parse_csv_list(
            os.getenv("CORS_ALLOW_ORIGINS"),
            ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173", "http://localhost:8501"],
        ),
        auth_username=os.getenv("AUTH_USERNAME", "admin"),
        auth_password_hash=os.getenv("AUTH_PASSWORD_HASH", ""),
        job_queue_backend=(os.getenv("JOB_QUEUE_BACKEND", "memory").strip().lower() or "memory"),
        redis_url=(os.getenv("REDIS_URL", "").strip()),
        redis_queue_name=(os.getenv("REDIS_QUEUE_NAME", "pea:jobs").strip() or "pea:jobs"),
        upload_retention_hours=max(1, _int_env("UPLOAD_RETENTION_HOURS", 72)),
        login_rate_max_attempts=max(1, _int_env("LOGIN_RATE_MAX_ATTEMPTS", 10)),
        login_rate_window_seconds=max(10, _int_env("LOGIN_RATE_WINDOW_SECONDS", 300)),
        expose_internal_error_details=_bool_env("EXPOSE_INTERNAL_ERROR_DETAILS", False),
    )
