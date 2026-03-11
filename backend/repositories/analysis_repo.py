from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import asc, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.tables import EmailAnalysis


class AnalysisRepository:
    def get_by_id(self, db: Session, analysis_id: str) -> Optional[EmailAnalysis]:
        return db.get(EmailAnalysis, analysis_id)

    def get_existing(self, db: Session, message_id: str | None, fingerprint: str) -> Optional[EmailAnalysis]:
        if message_id:
            stmt = (
                select(EmailAnalysis)
                .where(EmailAnalysis.message_id == message_id)
                .order_by(desc(EmailAnalysis.created_at))
                .limit(1)
            )
            hit = db.execute(stmt).scalar_one_or_none()
            if hit:
                return hit

        stmt = select(EmailAnalysis).where(EmailAnalysis.fingerprint == fingerprint).limit(1)
        return db.execute(stmt).scalar_one_or_none()

    def create(self, db: Session, payload: dict) -> EmailAnalysis:
        obj = EmailAnalysis(
            id=payload["id"],
            message_id=payload.get("message_id"),
            fingerprint=payload["fingerprint"],
            sender=payload.get("sender"),
            recipient=payload.get("recipient"),
            subject=payload.get("subject"),
            parsed_email=payload.get("parsed_email"),
            url_extraction=payload.get("url_extraction"),
            url_reputation=payload.get("url_reputation"),
            url_analysis=payload.get("url_analysis"),
            content_review=payload.get("content_review"),
            attachment_analysis=payload.get("attachment_analysis"),
            decision=payload.get("decision"),
            report_markdown=payload.get("report_markdown"),
            report_path=payload["report_path"],
            execution_trace=payload.get("execution_trace"),
            review_label=payload.get("review_label"),
            review_note=payload.get("review_note"),
            reviewed_by=payload.get("reviewed_by"),
            reviewed_at=payload.get("reviewed_at"),
            created_at=payload.get("created_at", datetime.now(timezone.utc)),
        )
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Handle duplicate fingerprint race by returning existing row.
            existing = self.get_existing(db, payload.get("message_id"), payload["fingerprint"])
            if existing:
                return existing
            raise
        db.refresh(obj)
        return obj

    def _apply_filters(
        self,
        stmt,
        *,
        sender: str | None = None,
        subject: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ):
        if sender:
            stmt = stmt.where(EmailAnalysis.sender.contains(sender))
        if subject:
            stmt = stmt.where(EmailAnalysis.subject.contains(subject))
        if created_from:
            stmt = stmt.where(EmailAnalysis.created_at >= created_from)
        if created_to:
            stmt = stmt.where(EmailAnalysis.created_at <= created_to)
        return stmt

    def list(
        self,
        db: Session,
        *,
        sender: str | None = None,
        subject: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[EmailAnalysis], int]:
        sortable_fields = {
            "created_at": EmailAnalysis.created_at,
            "sender": EmailAnalysis.sender,
            "subject": EmailAnalysis.subject,
        }
        order_col = sortable_fields.get(sort_by, EmailAnalysis.created_at)
        order_fn = asc if sort_order == "asc" else desc

        list_stmt = self._apply_filters(
            select(EmailAnalysis),
            sender=sender,
            subject=subject,
            created_from=created_from,
            created_to=created_to,
        ).order_by(order_fn(order_col), desc(EmailAnalysis.created_at)).offset(offset).limit(limit)

        count_stmt = self._apply_filters(
            select(func.count()).select_from(EmailAnalysis),
            sender=sender,
            subject=subject,
            created_from=created_from,
            created_to=created_to,
        )

        rows = list(db.execute(list_stmt).scalars().all())
        total = int(db.execute(count_stmt).scalar_one() or 0)
        return rows, total
