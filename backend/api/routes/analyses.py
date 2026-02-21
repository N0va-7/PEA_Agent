from datetime import datetime

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from backend.api.deps import get_container, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.schemas.analysis import AnalysisListResponse, AnalysisResponse
from backend.schemas.jobs import JobCreateResponse


router = APIRouter(prefix="/analyses", tags=["analyses"], dependencies=[Depends(require_auth)])
MAX_EML_BYTES = 10 * 1024 * 1024
ALLOWED_SORT_FIELDS = {"created_at", "sender", "subject"}
ALLOWED_SORT_ORDER = {"asc", "desc"}



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
