from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()


def _is_sqlite_url(db_url: str) -> bool:
    return db_url.strip().lower().startswith("sqlite:")



def create_engine_and_session(db_path: Path | None = None, db_url: str | None = None):
    effective_path = db_path or Path("./runtime/db/analysis.db")
    effective_url = (db_url or f"sqlite:///{effective_path}").strip()

    kwargs = {"future": True}
    if _is_sqlite_url(effective_url):
        effective_path.parent.mkdir(parents=True, exist_ok=True)
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_pre_ping"] = True

    engine = create_engine(
        effective_url,
        **kwargs,
    )
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine, session_factory



def init_db(engine):
    from backend.models import tables  # noqa: F401

    Base.metadata.create_all(bind=engine)
