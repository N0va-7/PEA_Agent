from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.tables import UrlAnalysis


class UrlAnalysisRepository:
    def get_by_id(self, db: Session, analysis_id: str) -> Optional[UrlAnalysis]:
        return db.get(UrlAnalysis, analysis_id)

    def get_existing(self, db: Session, url_hash: str) -> Optional[UrlAnalysis]:
        stmt = select(UrlAnalysis).where(UrlAnalysis.url_hash == url_hash).limit(1)
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, payload: dict) -> UrlAnalysis:
        now = payload.get("created_at", datetime.now(timezone.utc))
        obj = UrlAnalysis(
            id=payload["id"],
            url_hash=payload["url_hash"],
            requested_url=payload.get("requested_url"),
            normalized_url=payload["normalized_url"],
            url_reputation=payload.get("url_reputation"),
            url_analysis=payload.get("url_analysis"),
            decision=payload.get("decision"),
            execution_trace=payload.get("execution_trace"),
            request_count=int(payload.get("request_count") or 1),
            created_at=now,
            updated_at=payload.get("updated_at", now),
        )
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = self.get_existing(db, payload["url_hash"])
            if existing is not None:
                return existing
            raise
        db.refresh(obj)
        return obj

    def touch_existing(self, db: Session, obj: UrlAnalysis, *, requested_url: str | None = None) -> UrlAnalysis:
        obj.requested_url = requested_url or obj.requested_url
        obj.request_count = int(obj.request_count or 0) + 1
        obj.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(obj)
        return obj

    def list(self, db: Session, *, limit: int = 20, offset: int = 0) -> tuple[list[UrlAnalysis], int]:
        list_stmt = (
            select(UrlAnalysis)
            .order_by(desc(UrlAnalysis.updated_at), desc(UrlAnalysis.created_at))
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(UrlAnalysis)
        rows = list(db.execute(list_stmt).scalars().all())
        total = int(db.execute(count_stmt).scalar_one() or 0)
        return rows, total
