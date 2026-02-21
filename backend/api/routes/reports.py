from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from backend.api.deps import get_container, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error


router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_auth)])


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_report_path(raw_path: str, report_root: Path) -> Path | None:
    if not raw_path:
        return None

    candidate = Path(raw_path).expanduser().resolve(strict=False)
    if candidate.exists() and candidate.is_file() and _is_within_root(candidate, report_root):
        return candidate

    # Compatibility fallback for migrated records with legacy absolute paths.
    fallback = report_root / candidate.name
    if fallback.exists() and fallback.is_file():
        return fallback.resolve()

    return None


@router.get("/{analysis_id}")
def download_report(analysis_id: str, container: AppContainer = Depends(get_container)):
    analysis = container.analysis_service.get_analysis(analysis_id)
    if not analysis:
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="analysis_not_found", message="Analysis not found")

    report_root = container.settings.report_output_dir.resolve()
    report_path = _resolve_report_path(analysis.report_path, report_root)
    if not report_path:
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="report_not_found", message="Report file not found")

    return FileResponse(path=report_path, media_type="text/markdown", filename=report_path.name)
