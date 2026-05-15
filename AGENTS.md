## Learned User Preferences
- Do not inspect local `.env` files unless the user explicitly asks; use example files, docs, or ask the user to confirm values instead.
- When executing an attached plan, do not edit the plan file; use existing todos when provided, mark progress as work begins, and continue through the listed todos.

## Learned Workspace Facts
- Observability should stay dormant by default unless explicitly reactivated; avoid reintroducing local Grafana/Prometheus/Loki or enabling OTEL/Grafana Cloud automatically.
- The root/status page should avoid `healthz`/`readyz` endpoint labels and duplicate DB rows; readiness already covers DB, and the public spec button copy should be `openAPI`.
