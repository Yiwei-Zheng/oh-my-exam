# Oh-My-Exam

Oh-My-Exam is a bilingual web workspace for browsing exam questions and running the server-side ingestion pipeline. The maintained applications are `frontend/` and `backend/`; legacy desktop GUIs and root-level tool packages have been removed.

## Repository

```text
frontend/   Next.js + shadcn browser application
backend/    FastAPI API, pipeline code, configuration, resources, PDFs and databases
assets/     maintained shared design assets
tmp/        disposable local scratch files
docs/       product, architecture, operations and decisions
deploy/     Linux systemd and Caddy examples
scripts/    repository-wide setup and start commands
```

Runtime data belongs under `backend/data/`. Original PDFs remain authoritative. Question and answer previews are clipped dynamically from PDFs; permanent JPG crops are not produced by the new application.

## Development

Prepare the existing project environment, then run the unified launcher from
the repository root:

```powershell
python scripts\setup_env.py --group all
Set-Location frontend
npm install
Set-Location ..
python start_server.py
```

On Windows, `start-dev.cmd` is also available for double-click startup. Press
Ctrl+C to stop both servers together. Pass `--lan` to listen on the local network.

Open `http://127.0.0.1:4173`. On first API start, configure an administrator with the variables shown in `.env.example`. The admin workspace provides the exam tree, question-level and full-paper PDF previews, extracted answer text, versioned corrections and catalog-release pipeline control.

## Pipeline CLI

Pipeline packages live below `backend/src/oh_my_exam/pipelines/` and remain callable without the Web GUI. Install the backend package in editable mode to expose these commands:

```text
ome-cie-alevel-downloader
ome-cie-alevel-splitter
ome-uat-admissions-downloader
ome-uat-admissions-splitter
ome-process-tmua
ome-pat-admissions-downloader
ome-pat-admissions-splitter
ome-step-admissions-downloader
ome-step-admissions-splitter
ome-pack-subject
ome-build-catalog
```

Run `COMMAND --help` for adapter-specific options. Defaults resolve to `backend/data`, `backend/config` and `backend/resources`, independent of the current working directory.

TMUA has a reproducible end-to-end command. It discovers and downloads the official archive, splits question papers and worked answers, verifies each answer against the official key, packages the portable subject database, rebuilds classifications and similar-question recommendations, then atomically activates the global catalog:

```powershell
Set-Location backend
..\.venv\Scripts\python scripts\process_tmua.py
```

Use `--skip-download` to rebuild from the immutable PDFs already under `backend/data/raw_papers`, or `--skip-activate` to stop after producing the portable TMUA database. The command is idempotent and may be rerun after new official papers are downloaded.

## Verification

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest -q
Set-Location ..\frontend
npm run lint
npm run typecheck
npm run build
```

Production deployment is Linux bare-metal with Caddy and systemd. Docker is intentionally out of scope. See [the documentation index](docs/index.md) and [Linux deployment guide](docs/operations/linux-deployment.md).
