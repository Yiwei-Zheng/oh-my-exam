# Linux Bare-Metal Deployment

Docker is not supported in this iteration. The reference deployment uses a dedicated `oh-my-exam` Unix account, `/srv/oh-my-exam`, a project virtual environment, systemd and Caddy.

## Install

```bash
sudo useradd --system --home /srv/oh-my-exam --shell /usr/sbin/nologin oh-my-exam
sudo mkdir -p /srv/oh-my-exam /etc/oh-my-exam
sudo chown -R oh-my-exam:oh-my-exam /srv/oh-my-exam
python3 -m venv /srv/oh-my-exam/.venv
/srv/oh-my-exam/.venv/bin/pip install -e '/srv/oh-my-exam/backend[test]'
cd /srv/oh-my-exam/frontend && npm ci && npm run build
```

Copy `.env.example` to `/etc/oh-my-exam/oh-my-exam.env`, set production secrets, and set `OME_SECURE_COOKIES=true`. The environment file must be readable only by the service account and administrators.

The reference one-worker service uses process-local login rate-limit storage.
Before configuring multiple API workers, install
`backend[rate-limit-redis]`, run Redis as a native or managed service, and set
`OME_LOGIN_RATE_LIMIT_STORAGE_URI` to its protected Redis URI.

Install `deploy/systemd/oh-my-exam-api.service` and adapt the domain in `deploy/caddy/Caddyfile`. Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now oh-my-exam-api
sudo systemctl reload caddy
curl --fail https://exam.example.com/api/v1/health
```

## Upgrade

Stop the API, back up `backend/data`, update source and dependencies, run `backend/scripts/migrate_catalog_schema.py` against the active catalog, rebuild the frontend, then restart the API. Keep the backup until health, login, tree browsing, question PDF and pipeline activation checks pass.

## Backup and restore

Back up the whole private `backend/data` tree while the API is stopped, or use SQLite's online backup API for live databases and independently snapshot immutable PDFs. Restore databases and PDFs as one consistent set. Never restore generated JPG crops; the current application does not use them.
