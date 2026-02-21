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


@dataclass(frozen=True)
class Settings:
    sqlite_db_path: Path
    report_output_dir: Path
    upload_dir: Path
    model_dir: Path

    llm_api_key: str
    llm_base_url: str
    llm_model_id: str

    threatbook_api_key: str

    jwt_secret_key: str
    jwt_algorithm: str
    jwt_expire_hours: int

    cors_allow_origins: list[str]

    auth_username: str
    auth_password_hash: str



def load_settings() -> Settings:
    sqlite_db_path = Path(os.getenv("SQLITE_DB_PATH", str(DEFAULT_RUNTIME_DIR / "db" / "analysis.db"))).expanduser()
    report_output_dir = Path(os.getenv("REPORT_OUTPUT_DIR", str(DEFAULT_RUNTIME_DIR / "reports"))).expanduser()
    upload_dir = Path(os.getenv("UPLOAD_DIR", str(DEFAULT_RUNTIME_DIR / "uploads"))).expanduser()
    model_dir = Path(os.getenv("MODEL_DIR", str(DEFAULT_MODEL_DIR))).expanduser()

    return Settings(
        sqlite_db_path=sqlite_db_path,
        report_output_dir=report_output_dir,
        upload_dir=upload_dir,
        model_dir=model_dir,
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_base_url=_normalize_llm_base_url(os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")),
        llm_model_id=os.getenv("LLM_MODEL_ID", "gpt-4o-mini"),
        threatbook_api_key=os.getenv("THREATBOOK_API_KEY", ""),
        jwt_secret_key=os.getenv("JWT_SECRET_KEY", "change-me"),
        jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
        jwt_expire_hours=_int_env("JWT_EXPIRE_HOURS", 8),
        cors_allow_origins=_parse_csv_list(
            os.getenv("CORS_ALLOW_ORIGINS"),
            ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8501"],
        ),
        auth_username=os.getenv("AUTH_USERNAME", "admin"),
        auth_password_hash=os.getenv("AUTH_PASSWORD_HASH", ""),
    )
