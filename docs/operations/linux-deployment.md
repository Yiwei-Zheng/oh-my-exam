# Linux Bare-Metal Deployment

## Target

Production targets supported Ubuntu and Debian releases with systemd. Docker is
not supported in the current iteration.

## Components

- Caddy serves `frontend/dist` and proxies `/api/*`.
- `ome-api.service` runs FastAPI from the project virtual environment.
- `ome-worker.service` runs Celery workers.
- PostgreSQL and Redis run locally or as managed services.
- Original documents use the configured filesystem or S3-compatible store.

## Required procedures

`deploy/` must provide repeatable installation, configuration validation,
database migration, backup, upgrade, health check, and systemd unit installation.
Secrets remain outside the repository. Services run as a dedicated unprivileged
account and receive only required filesystem access.

The final runbook will contain verified commands after deployment assets exist.
It must cover fresh installation, repeated installation, service restart,
database migration, pipeline execution, frontend routing, SSE, PDF ranges, TLS,
backup, and restore.
