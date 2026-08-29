# Development

## Prerequisites

- Python 3.11 or later
- Node.js 20.17 or later
- npm
- Tesseract on `PATH` only when OCR fallback is required

From the repository root, prepare the Python environment and install frontend dependencies:

```powershell
python scripts\setup_env.py --group all
Set-Location frontend
npm install
```

Start the API from the repository root:

```powershell
$env:OME_BOOTSTRAP_ADMIN_EMAIL = 'admin@example.com'
$env:OME_BOOTSTRAP_ADMIN_PASSWORD = 'replace-this-development-password'
python scripts\start_api.py
```

The bootstrap variables are needed only until the first administrator exists.
Local development creates and reuses `backend/data/application.secret` when
`OME_JWT_SECRET` is omitted. Production must provide an explicit secret through
the protected systemd environment file.

Start Vite from `frontend/`:

```powershell
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Use `VITE_API_PROXY_TARGET` to override it.

## Validation

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
Set-Location ..\frontend
npm run lint
npm run typecheck
npm run test
npm run build
```

Pipeline CLIs are listed in the root README. The release pipeline can be exercised directly with `python backend/scripts/release_catalog.py`; it activates a candidate only after validation.
