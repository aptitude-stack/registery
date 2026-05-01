"""Default service landing page."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["root"])

ROOT_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Aptitude Registry - Work in Progress</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #11130f;
      --panel: #f4efe1;
      --ink: #171914;
      --muted: #5c6256;
      --line: #c6b98c;
      --accent: #d94f2b;
      --accent-dark: #7c2619;
      --green: #3e7b49;
    }

    * {
      box-sizing: border-box;
    }

    body {
      min-height: 100vh;
      margin: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      background:
        linear-gradient(90deg, rgba(244, 239, 225, 0.04) 1px, transparent 1px),
        linear-gradient(rgba(244, 239, 225, 0.04) 1px, transparent 1px),
        radial-gradient(circle at 72% 20%, rgba(217, 79, 43, 0.2), transparent 26%),
        var(--bg);
      background-size: 44px 44px, 44px 44px, auto, auto;
      color: var(--panel);
      font-family: ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
    }

    main {
      width: min(100%, 880px);
      border: 1px solid rgba(244, 239, 225, 0.22);
      background: var(--panel);
      color: var(--ink);
      box-shadow: 16px 16px 0 rgba(217, 79, 43, 0.85);
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: #e7dec3;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 0.78rem;
      color: var(--muted);
    }

    .mark {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      color: var(--ink);
      font-weight: 800;
    }

    .mark::before {
      content: "";
      width: 12px;
      height: 12px;
      background: var(--accent);
      box-shadow: 6px 6px 0 var(--accent-dark);
    }

    section {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 220px;
      gap: 32px;
      padding: clamp(28px, 6vw, 56px);
    }

    h1 {
      max-width: 12ch;
      margin: 0 0 18px;
      font-family: Georgia, "Times New Roman", serif;
      font-size: clamp(3rem, 10vw, 7.5rem);
      font-weight: 900;
      line-height: 0.82;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    p {
      max-width: 58ch;
      margin: 0;
      color: var(--muted);
      font-size: 1rem;
      line-height: 1.7;
    }

    .status {
      align-self: end;
      display: grid;
      gap: 10px;
      padding-top: 10px;
      border-top: 3px solid var(--ink);
    }

    .status a,
    .status span {
      display: flex;
      align-items: center;
      justify-content: space-between;
      min-height: 42px;
      border-bottom: 1px solid var(--line);
      color: var(--ink);
      text-decoration: none;
      font-size: 0.88rem;
      font-weight: 700;
    }

    .status a::after,
    .status span::after {
      content: "OK";
      color: var(--green);
      font-size: 0.76rem;
    }

    @media (max-width: 720px) {
      body {
        place-items: stretch;
      }

      main {
        box-shadow: 8px 8px 0 rgba(217, 79, 43, 0.85);
      }

      header,
      section {
        grid-template-columns: 1fr;
      }

      section {
        gap: 28px;
      }

      h1 {
        max-width: 9ch;
      }
    }
  </style>
</head>
<body>
  <main aria-labelledby="page-title">
    <header>
      <span class="mark">Aptitude Registry</span>
      <span>Default service page</span>
    </header>
    <section>
      <div>
        <h1 id="page-title">Work In Progress</h1>
        <p>
          This registry service is online, but the public product surface is still
          being shaped. Use the operational endpoints below for liveness and
          dependency readiness.
        </p>
      </div>
      <nav class="status" aria-label="Operational endpoints">
        <a href="/healthz">/healthz</a>
        <a href="/readyz">/readyz</a>
        <span>API routes active</span>
      </nav>
    </section>
  </main>
</body>
</html>
"""


@router.get("/", response_class=HTMLResponse)
def get_root() -> HTMLResponse:
    """Return the default work-in-progress service page."""
    return HTMLResponse(ROOT_PAGE_HTML)
