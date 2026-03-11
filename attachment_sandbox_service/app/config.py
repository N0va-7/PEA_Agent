from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SANDBOX_", extra="ignore")

    app_name: str = "Attachment Analysis Sandbox"
    app_version: str = "0.2.0"

    database_url: str = "sqlite+aiosqlite:///./sandbox.db"
    queue_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"
    redis_queue_name: str = "analysis_jobs"

    object_store_backend: str = "filesystem"
    object_store_root: str = ".sandbox-data/objects"

    rules_root: str = "rules"
    compiled_rules_path: str = ".sandbox-data/compiled/default_rules.yarc"

    embedded_worker: bool = True
    worker_count: int = 2
    worker_poll_seconds: float = 0.5
    stale_job_after_seconds: int = 300
    analysis_timeout_seconds: float = 2.5

    max_file_size_bytes: int = 25 * 1024 * 1024
    max_archive_depth: int = 3
    max_archive_entries: int = 128
    max_archive_total_uncompressed: int = 64 * 1024 * 1024
    max_archive_entry_size: int = 8 * 1024 * 1024

    clamav_enabled: bool = False
    clamav_host: str = "localhost"
    clamav_port: int = 3310
    clamav_timeout_seconds: float = 2.0

    @property
    def object_store_path(self) -> Path:
        return Path(self.object_store_root)
