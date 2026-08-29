# Development

## Supported environment

Windows and Linux are supported for source development. Linux is required for
production-equivalent Celery worker verification.

## Services

Development requires PostgreSQL and Redis, the FastAPI application, a Celery
worker, and the Vite frontend. All processes use the typed environment contract
documented by `.env.example`.

Exact installation and start commands will be finalized when the source move is
complete. Documentation must describe only commands verified against the new
paths; legacy `web/` and `tools/` commands are intentionally not preserved.

## Verification

Run the narrowest relevant unit and integration tests during development. The
clean-cut gate additionally runs backend tests and migrations, frontend test,
type check, lint, build, accessibility and E2E checks, representative PDF
rendering, and one complete CIE 9709 pipeline.
