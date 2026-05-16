"""Default service landing page."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse

router = APIRouter(tags=["root"])

_ROOT_PAGE_PATH = Path(__file__).parent / "resource" / "root.html"
_FAVICON_PATH = Path(__file__).parent / "resource" / "favicon.svg"
ROOT_PAGE_HTML: Final[str] = _ROOT_PAGE_PATH.read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def get_root() -> HTMLResponse:
    """Return the default service status page."""
    return HTMLResponse(content=ROOT_PAGE_HTML, media_type="text/html")


@router.get("/favicon.svg", include_in_schema=False)
def get_favicon() -> FileResponse:
    """Return the registry favicon asset."""
    return FileResponse(_FAVICON_PATH, media_type="image/svg+xml")
