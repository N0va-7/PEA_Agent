from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse


DEMO_PAGE = Path(__file__).resolve().parent / "templates" / "demo.html"


def demo_page_response() -> FileResponse:
    return FileResponse(DEMO_PAGE, media_type="text/html; charset=utf-8")
