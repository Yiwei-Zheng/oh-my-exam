# 0009: Linux bare-metal deployment

## Status

Accepted on 2026-08-29.

## Context

The application must run directly on a server. Docker support was considered
and explicitly removed from the current scope.

## Decision

Support current Ubuntu and Debian releases using source checkout, a project
Python virtual environment, a production frontend build, Caddy, and systemd.
The deployed services are:

- `ome-api.service`: FastAPI application.
- Backend-owned pipeline subprocesses launched by the API service.
- SQLite databases and original PDFs below the protected backend data root.
- Caddy serving frontend static assets and proxying `/api/` to FastAPI.

Provide idempotent native installation, database migration, upgrade, backup,
health-check, and service unit assets under `deploy/`. All application settings
come from the same typed environment contract used in development.

Do not add Dockerfiles, Compose files, Docker-specific code paths, or Docker
acceptance tests in this iteration. Preserve stateless service and externalized
configuration boundaries so container support can be added later without a
business-layer rewrite.

## Consequences

- Linux with systemd is the production target.
- Windows remains a supported development environment, not a production target.
- Native deployment tests must cover fresh installation, repeat installation,
  migrations, service restart, pipeline execution, and PDF range requests.

## References

- Caddy static frontend and API reverse proxy pattern:
  https://caddyserver.com/docs/caddyfile/patterns
