from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy import delete, select

from backend.api.deps import get_container, get_current_user, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.models.tables import AnalysisFeedbackEvent, EmailAnalysis
from backend.schemas.analysis import AnalysisDeleteResponse, AnalysisListResponse, AnalysisResponse
from backend.schemas.feedback import FeedbackEventResponse, FeedbackResponse, FeedbackUpsertRequest
from backend.schemas.jobs import JobCreateResponse


router = APIRouter(prefix="/analyses", tags=["analyses"], dependencies=[Depends(require_auth)])
MAX_EML_BYTES = 10 * 1024 * 1024
ALLOWED_SORT_FIELDS = {"created_at", "sender", "subject"}
ALLOWED_SORT_ORDER = {"asc", "desc"}


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _cleanup_report_file(raw_path: str | None, report_root: Path):
    if not raw_path:
        return
    try:
        path = Path(raw_path).expanduser().resolve(strict=False)
    except Exception:
        return
    candidates = []
    if _is_within_root(path, report_root):
        candidates.append(path)
    candidates.append(report_root / path.name)
    for target in candidates:
        try:
            if target.exists() and target.is_file() and _is_within_root(target.resolve(), report_root):
                target.unlink(missing_ok=True)
                break
        except Exception:
            continue



def _to_analysis_response(obj) -> AnalysisResponse:
    return AnalysisResponse(
        id=obj.id,
        message_id=obj.message_id,
        fingerprint=obj.fingerprint,
        sender=obj.sender,
        recipient=obj.recipient,
        subject=obj.subject,
        url_analysis=obj.url_analysis,
        body_analysis=obj.body_analysis,
        attachment_analysis=obj.attachment_analysis,
        final_decision=obj.final_decision,
        llm_report=obj.llm_report,
        report_path=obj.report_path,
        execution_trace=obj.execution_trace,
        review_label=obj.review_label,
        review_note=obj.review_note,
        reviewed_by=obj.reviewed_by,
        reviewed_at=obj.reviewed_at,
        created_at=obj.created_at,
    )


@router.post("", response_model=JobCreateResponse)
async def create_analysis_job(
    file: UploadFile = File(...),
    container: AppContainer = Depends(get_container),
):
    if not file.filename or not file.filename.lower().endswith(".eml"):
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_file_type",
            message="Only .eml file is supported",
        )

    raw_eml = await file.read()
    if not raw_eml:
        raise_api_error(status_code=status.HTTP_400_BAD_REQUEST, code="empty_file", message="Empty file")
    if len(raw_eml) > MAX_EML_BYTES:
        raise_api_error(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            code="file_too_large",
            message=f"File too large (max {MAX_EML_BYTES} bytes).",
        )

    job_id = container.analysis_service.submit_job(raw_eml)
    container.job_runner.submit(job_id, raw_eml)

    return JobCreateResponse(job_id=job_id, status="queued")


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(analysis_id: str, container: AppContainer = Depends(get_container)):
    analysis = container.analysis_service.get_analysis(analysis_id)
    if not analysis:
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="analysis_not_found", message="Analysis not found")
    return _to_analysis_response(analysis)


@router.get("", response_model=AnalysisListResponse)
def list_analyses(
    sender: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    limit: int = Query(default=20, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    container: AppContainer = Depends(get_container),
):
    try:
        dt_from = datetime.fromisoformat(created_from) if created_from else None
        dt_to = datetime.fromisoformat(created_to) if created_to else None
    except ValueError as exc:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_datetime",
            message="created_from/created_to must be ISO datetime strings.",
        )

    if sort_by not in ALLOWED_SORT_FIELDS:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_sort_by",
            message=f"sort_by must be one of {sorted(ALLOWED_SORT_FIELDS)}",
        )
    if sort_order not in ALLOWED_SORT_ORDER:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_sort_order",
            message="sort_order must be one of ['asc', 'desc']",
        )

    # Prefer page/page_size when provided; keep limit/offset for backward compatibility.
    effective_limit = page_size if page_size != 20 or page != 1 else limit
    effective_offset = (page - 1) * effective_limit if page != 1 or page_size != 20 else offset

    rows, total = container.analysis_service.list_analyses(
        sender=sender,
        subject=subject,
        created_from=dt_from,
        created_to=dt_to,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=effective_limit,
        offset=effective_offset,
    )
    current_page = (effective_offset // effective_limit) + 1
    return AnalysisListResponse(
        items=[_to_analysis_response(row) for row in rows],
        total=total,
        page=current_page,
        page_size=effective_limit,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=effective_limit,
        offset=effective_offset,
    )


@router.delete("/{analysis_id}", response_model=AnalysisDeleteResponse)
def delete_analysis(
    analysis_id: str,
    container: AppContainer = Depends(get_container),
):
    report_root = container.settings.report_output_dir.resolve()
    report_path: str | None = None
    with container.analysis_service.session_factory() as db:
        analysis = container.analysis_service.analysis_repo.get_by_id(db, analysis_id)
        if not analysis:
            raise_api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="analysis_not_found",
                message="Analysis not found",
            )
        report_path = analysis.report_path
        db.execute(delete(AnalysisFeedbackEvent).where(AnalysisFeedbackEvent.analysis_id == analysis_id))
        db.delete(analysis)
        db.commit()

    _cleanup_report_file(report_path, report_root)
    return AnalysisDeleteResponse(deleted_count=1)


@router.delete("", response_model=AnalysisDeleteResponse)
def clear_analyses(
    container: AppContainer = Depends(get_container),
):
    report_root = container.settings.report_output_dir.resolve()
    report_paths: list[str] = []
    with container.analysis_service.session_factory() as db:
        report_paths = [
            row[0]
            for row in db.execute(select(EmailAnalysis.report_path)).all()
            if row and row[0]
        ]
        deleted_count = len(report_paths)
        db.execute(delete(AnalysisFeedbackEvent))
        db.execute(delete(EmailAnalysis))
        db.commit()

    for report_path in report_paths:
        _cleanup_report_file(report_path, report_root)
    return AnalysisDeleteResponse(deleted_count=deleted_count)


@router.post("/{analysis_id}/feedback", response_model=FeedbackResponse)
def upsert_feedback(
    analysis_id: str,
    payload: FeedbackUpsertRequest,
    container: AppContainer = Depends(get_container),
    current_user: str = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    with container.analysis_service.session_factory() as db:
        analysis = container.analysis_service.analysis_repo.get_by_id(db, analysis_id)
        if not analysis:
            raise_api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="analysis_not_found",
                message="Analysis not found",
            )

        event = AnalysisFeedbackEvent(
            id=str(uuid4()),
            analysis_id=analysis_id,
            old_review_label=analysis.review_label,
            new_review_label=payload.review_label,
            old_review_note=analysis.review_note,
            new_review_note=payload.review_note,
            changed_by=current_user,
            changed_at=now,
        )
        analysis.review_label = payload.review_label
        analysis.review_note = payload.review_note
        analysis.reviewed_by = current_user
        analysis.reviewed_at = now
        db.add(event)
        db.commit()
        db.refresh(analysis)

    return FeedbackResponse(
        analysis_id=analysis_id,
        review_label=analysis.review_label or payload.review_label,
        review_note=analysis.review_note,
        reviewed_by=analysis.reviewed_by or current_user,
        reviewed_at=analysis.reviewed_at or now,
    )


@router.get("/{analysis_id}/feedback-history", response_model=list[FeedbackEventResponse])
def get_feedback_history(
    analysis_id: str,
    container: AppContainer = Depends(get_container),
):
    with container.analysis_service.session_factory() as db:
        analysis = container.analysis_service.analysis_repo.get_by_id(db, analysis_id)
        if not analysis:
            raise_api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                code="analysis_not_found",
                message="Analysis not found",
            )

        stmt = (
            select(AnalysisFeedbackEvent)
            .where(AnalysisFeedbackEvent.analysis_id == analysis_id)
            .order_by(AnalysisFeedbackEvent.changed_at.desc())
        )
        rows = list(db.execute(stmt).scalars().all())

    return [
        FeedbackEventResponse(
            id=row.id,
            analysis_id=row.analysis_id,
            old_review_label=row.old_review_label,
            new_review_label=row.new_review_label,
            old_review_note=row.old_review_note,
            new_review_note=row.new_review_note,
            changed_by=row.changed_by,
            changed_at=row.changed_at,
        )
        for row in rows
    ]
