# Development

## Prerequisites

- Python 3.11 or later
- Node.js 20.19 or later
- npm
- Tesseract on `PATH` only when OCR fallback is required

From the repository root, prepare the Python environment and install frontend dependencies:

```powershell
python scripts\setup_env.py --group all
Set-Location frontend
npm install
```

Start the complete development application from the repository root:

```powershell
$env:OME_BOOTSTRAP_ADMIN_EMAIL = 'admin@example.com'
$env:OME_BOOTSTRAP_ADMIN_PASSWORD = 'replace-this-development-password'
.\start-dev.cmd
```

The bootstrap variables are needed only until the first administrator exists.
Local development creates and reuses `backend/data/application.secret` when
`OME_JWT_SECRET` is omitted. Production must provide an explicit secret through
the protected systemd environment file.

The launcher starts the API on port 8000 and Next.js on port 4173, streams both
logs into one terminal, and stops both process trees on Ctrl+C. By default both
servers listen on all interfaces. The launcher prints the detected LAN address
and a terminal QR code that opens the frontend from another device on the same
network. The same launcher works on every supported platform through Python:

```bash
python start_server.py
```

Next.js proxies `/api` to `http://127.0.0.1:8000`. Use `OME_API_PROXY_TARGET` to override it.
Use `python start_server.py --check` for a non-starting prerequisite and port
check. Use `python start_server.py --local` when the servers must only be
reachable from the current computer. The legacy `--lan` option remains accepted
but is no longer necessary.

LAN access can still be blocked by the host firewall or wireless client
isolation. Allow Python and Node.js on private networks when the operating system
prompts for firewall access.

## Validation

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
Set-Location ..\frontend
npm run lint
npm run typecheck
npm run build
```

Pipeline CLIs are listed in the root README. The release pipeline can be exercised directly with `python backend/scripts/release_catalog.py`; it activates a candidate only after validation.
