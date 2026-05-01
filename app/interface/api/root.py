"""Default service landing page."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["root"])

_ROOT_PAGE_PATH = Path(__file__).parent / "resource" / "root.html"
ROOT_PAGE_HTML = _ROOT_PAGE_PATH.read_text(encoding="utf-8")


@router.get("/", response_class=HTMLResponse)
def get_root() -> HTMLResponse:
    """Return the default service status page."""
    return HTMLResponse(ROOT_PAGE_HTML)
