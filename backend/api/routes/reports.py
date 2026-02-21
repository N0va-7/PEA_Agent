from pathlib import Path

from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse

from backend.api.deps import get_container, require_auth
from backend.container import AppContainer
from backend.infra.errors import raise_api_error


router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_auth)])


@router.get("/{analysis_id}")
def download_report(analysis_id: str, container: AppContainer = Depends(get_container)):
    analysis = container.analysis_service.get_analysis(analysis_id)
    if not analysis:
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="analysis_not_found", message="Analysis not found")

    report_path = Path(analysis.report_path).resolve()
    report_root = container.settings.report_output_dir.resolve()
    if report_root not in report_path.parents:
        raise_api_error(status_code=status.HTTP_400_BAD_REQUEST, code="invalid_report_path", message="Invalid report path")
    if not report_path.exists() or not report_path.is_file():
        raise_api_error(status_code=status.HTTP_404_NOT_FOUND, code="report_not_found", message="Report file not found")

    return FileResponse(path=report_path, media_type="text/markdown", filename=report_path.name)
