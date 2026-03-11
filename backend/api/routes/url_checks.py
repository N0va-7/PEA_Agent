from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Query, status

from backend.agent_tools.decision_engine import make_decision_engine_tool
from backend.agent_tools.url_extractor import _normalize_url
from backend.agent_tools.url_model_analysis import make_url_model_analysis_tool
from backend.agent_tools.url_reputation_vt import _url_hash, make_url_reputation_vt_tool
from backend.api.deps import get_container, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error
from backend.repositories.url_analysis_repo import UrlAnalysisRepository
from backend.schemas.url_check import (
    URLCheckBatchResponse,
    URLCheckListResponse,
    URLCheckRequest,
    URLCheckResponse,
    URLToolOutputsPayload,
)


router = APIRouter(prefix="/url-checks", tags=["url-checks"], dependencies=[Depends(require_auth)])
url_analysis_repo = UrlAnalysisRepository()
MAX_URLS_PER_REQUEST = 20


def _to_url_check_response(obj, *, is_cached_result: bool = False) -> URLCheckResponse:
    return URLCheckResponse(
        id=obj.id,
        requested_url=obj.requested_url or obj.normalized_url,
        normalized_url=obj.normalized_url,
        tool_outputs=URLToolOutputsPayload(
            url_reputation=obj.url_reputation or {},
            url_analysis=obj.url_analysis or {},
        ),
        decision=obj.decision or {},
        execution_trace=obj.execution_trace or [],
        request_count=int(obj.request_count or 1),
        is_cached_result=is_cached_result,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
    )


def _build_url_context(normalized_url: str) -> dict:
    return {"url_extraction": {"normalized_urls": [normalized_url]}}


def _run_url_analysis(container: AppContainer, normalized_url: str) -> dict:
    vt_tool = make_url_reputation_vt_tool(container.settings, container.analysis_service.session_factory)
    url_model_tool = make_url_model_analysis_tool(container.settings.model_dir)
    decision_tool = make_decision_engine_tool()

    context = _build_url_context(normalized_url)
    context.update(vt_tool.run(context))
    context.update(url_model_tool.run(context))
    context.update(
        decision_tool.run(
            {
                "url_reputation": context.get("url_reputation", {}) or {},
                "url_analysis": context.get("url_analysis", {}) or {},
                "content_review": {},
                "attachment_analysis": {},
            }
        )
    )
    context["execution_trace"] = ["url_reputation_vt", "url_model_analysis", "decision_engine"]
    return context


@router.post("", response_model=URLCheckBatchResponse)
def create_url_checks(
    payload: URLCheckRequest,
    container: AppContainer = Depends(get_container),
):
    raw_urls = [str(item or "").strip() for item in payload.urls if str(item or "").strip()]
    if not raw_urls:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="invalid_url",
            message="At least one http/https URL is required.",
        )
    if len(raw_urls) > MAX_URLS_PER_REQUEST:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="too_many_urls",
            message=f"At most {MAX_URLS_PER_REQUEST} URLs are allowed per request.",
        )

    normalized_inputs: list[tuple[str, str]] = []
    seen_hashes: set[str] = set()
    for raw_url in raw_urls:
        normalized_url = _normalize_url(raw_url)
        if not normalized_url:
            raise_api_error(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_url",
                message=f"Unsupported URL: {raw_url}",
            )
        url_hash = _url_hash(normalized_url)
        if url_hash in seen_hashes:
            continue
        seen_hashes.add(url_hash)
        normalized_inputs.append((raw_url, normalized_url))

    items: list[URLCheckResponse] = []
    reused_count = 0
    created_count = 0

    for requested_url, normalized_url in normalized_inputs:
        url_hash = _url_hash(normalized_url)
        with container.analysis_service.session_factory() as db:
            existing = url_analysis_repo.get_existing(db, url_hash)
            if existing is not None:
                existing = url_analysis_repo.touch_existing(db, existing, requested_url=requested_url)
                items.append(_to_url_check_response(existing, is_cached_result=True))
                reused_count += 1
                continue

        result = _run_url_analysis(container, normalized_url)
        with container.analysis_service.session_factory() as db:
            created = url_analysis_repo.create(
                db,
                {
                    "id": str(uuid4()),
                    "url_hash": url_hash,
                    "requested_url": requested_url,
                    "normalized_url": normalized_url,
                    "url_reputation": result.get("url_reputation", {}) or {},
                    "url_analysis": result.get("url_analysis", {}) or {},
                    "decision": result.get("decision", {}) or {},
                    "execution_trace": result.get("execution_trace", []) or [],
                    "request_count": 1,
                },
            )
            items.append(_to_url_check_response(created, is_cached_result=False))
            created_count += 1

    return URLCheckBatchResponse(
        items=items,
        submitted_count=len(items),
        reused_count=reused_count,
        created_count=created_count,
    )


@router.get("", response_model=URLCheckListResponse)
def list_url_checks(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    container: AppContainer = Depends(get_container),
):
    offset = (page - 1) * page_size
    with container.analysis_service.session_factory() as db:
        rows, total = url_analysis_repo.list(db, limit=page_size, offset=offset)
    return URLCheckListResponse(
        items=[_to_url_check_response(row, is_cached_result=False) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{analysis_id}", response_model=URLCheckResponse)
def get_url_check(analysis_id: str, container: AppContainer = Depends(get_container)):
    with container.analysis_service.session_factory() as db:
        obj = url_analysis_repo.get_by_id(db, analysis_id)
    if obj is None:
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="url_analysis_not_found", message="URL analysis not found")
    return _to_url_check_response(obj, is_cached_result=False)
