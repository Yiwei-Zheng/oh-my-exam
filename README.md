# Oh-My-Exam

This repository is starting with the local exam paper processing pipeline.

## Hosted API

The first hosted server slice lives in `web/backend/`. It exposes the existing
admissions-test subject packages through a read-only API and serves locally
retained PDFs by internal exam and paper ids. Authentication, PostgreSQL,
RAGFlow/DeepSeek, and the deterministic math harness currently return explicit
placeholder capability states rather than pretending to be available.

Create or update the shared development environment, then run the API from the
repository root. Use `python3` instead of `python` on Linux when required:

```console
python scripts/setup_env.py --group backend-dev
```

Windows:

```powershell
.venv\Scripts\python -m uvicorn oh_my_exam_server.main:app --reload --host 127.0.0.1 --port 8000
```

Linux/macOS:

```console
.venv/bin/python -m uvicorn oh_my_exam_server.main:app --reload --host 127.0.0.1 --port 8000
```

Useful endpoints:

- `GET http://127.0.0.1:8000/api/v1/health`
- `GET http://127.0.0.1:8000/api/v1/capabilities`
- `GET http://127.0.0.1:8000/api/v1/exams`
- `GET http://127.0.0.1:8000/docs`

Do not expose this initial server directly to the public internet because
authentication is still a documented placeholder.

## Official Web

The new Vue 3 + TypeScript client environment lives in `web/frontend/`. The
hosted API is its sibling under `web/backend/`; the two communicate only through
versioned HTTP APIs. The old React search implementation has been removed, and
the replacement product pages have not been implemented yet.

```powershell
Set-Location web\frontend
npm install
npm run dev
```

Frontend packages and npm cache stay under `web/frontend/`; no global npm
installation is required.

For a phone or tablet on the same trusted LAN, run `npm run dev:lan` and open
`http://<computer-ipv4>:4173/`. See
[`docs/modules/official-web.md`](docs/modules/official-web.md) for the visual
system, technical boundary, responsive strategy, and verification matrix.

## Exam Pipeline

The first local tools are split by responsibility:

- `tools/downloaders/alevel/cie/`: standalone CIE A-Level downloader.
- `tools/splitters/alevel/cie/`: standalone CIE A-Level splitter and SQLite ingestion tool.
- `tools/downloaders/admissions/uat/`: official ENGAA/NSAA archive downloader.
- `tools/splitters/admissions/uat/`: ENGAA/NSAA question and answer-key splitter.
- `tools/packers/`: standalone metadata packer that writes one SQLite database per subject.

These tools are intentionally decoupled. The downloader does not import splitter code, the splitter does not import downloader code, and the old combined `tools/exam_pipeline/` package has been removed.

Install the data-processing dependency group into the same root environment:

```console
python scripts/setup_env.py --group data-processing
```

This group includes the splitter OCR extra. Tesseract itself is an external
executable and must still be available on `PATH` when OCR fallback is used.

Common commands from the repository root:

```powershell
.venv\Scripts\python tools\splitters\alevel\cie\cie_alevel_splitters_cli.py init-db
.venv\Scripts\ome-cie-alevel-downloader discover-frank-assets --start-year 2001 --end-year 2026 --workers 4 --delay 0.2
.venv\Scripts\ome-cie-alevel-downloader sniff-frank-assets --subject 9709 --start-year 2002 --end-year 2025 --workers 4 --delay 0.2
.venv\Scripts\ome-cie-alevel-downloader crawl --limit 100 --delay 1.5 --workers 4
.venv\Scripts\ome-cie-alevel-downloader migrate-raw-layout
.venv\Scripts\python tools\splitters\alevel\cie\cie_alevel_splitters_cli.py split-downloaded --subject 9709 --start-year 2024 --end-year 2024 --workers 4
.venv\Scripts\python tools\splitters\alevel\cie\cie_alevel_splitters_cli.py backfill-content
.venv\Scripts\python tools\downloaders\admissions\uat\uat_admissions_downloader_cli.py
.venv\Scripts\python tools\splitters\admissions\uat\uat_admissions_splitter_cli.py
.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\a_level\cie --qualification a_level --exam-board cie --course-code 9231
```

Sync the current official Cambridge AS/A Level subject catalog and derived CIE downloader manifest:

```powershell
.venv\Scripts\python tools\downloaders\alevel\cie\sync_cambridge_catalog.py
```

Build or refresh the Frank availability table before large downloads:

```powershell
.venv\Scripts\ome-cie-alevel-downloader discover-frank-assets --start-year 2001 --end-year 2026 --workers 4 --delay 0.2
```

For day-to-day use, prefer per-subject sniffing:

```powershell
.venv\Scripts\ome-cie-alevel-downloader sniff-frank-assets --subject 9709 --start-year 2002 --end-year 2025 --workers 4 --delay 0.2
```

This writes files such as `resources/exam_boards/cie/available_assets/a_level/9709.json`. The GUI checks these files before downloading. If coverage for the selected subject/year range is missing, it automatically enables sniffing and refreshes only that subject/year range before downloading.

The older `discover-frank-assets` command still writes a single combined `resources/exam_boards/cie/frank_available_assets.json` snapshot, but the GUI workflow is now based on per-subject availability files. Pass `--ignore-availability` to `crawl` only when you intentionally want the older candidate-probing behavior.

Generated data is written under `data/` and should not be treated as source code.

Run the cross-platform downloader GUI from the repository root after activating the project Python environment:

```powershell
.venv\Scripts\python tools\downloaders\alevel\cie\cie_alevel_downloader_gui.py
```

The GUI reads subjects from `resources/exam_boards/cie/cie_a_level_subject_rules.json` when that file exists, then falls back to older CIE manifests. The subject selector has a search box and a scrollable list so all official subjects remain usable without hiding the download controls or output log. It supports system/light/dark theme modes, remembers the selected theme in `data/gui/cie_downloader_settings.json`, filters downloads through per-subject Frank asset files by default, automatically sniffs missing subject/year coverage, estimates crawl duration from selected file count, delay, and worker count, and provides configurable worker count for faster polite crawling. It only downloads raw CIE PDFs and writes status reports. It does not split papers. The intended workflow is:

1. Download all selected QP/MS PDFs into `data/raw_papers/`.
2. Review `data/reports/cie_download_status.jsonl` for downloaded, missing, failed, and rate-limited items.
3. Run splitting later as a separate batch step.

Run the local splitter GUI after raw PDFs exist:

```powershell
.venv\Scripts\python tools\splitters\alevel\cie\cie_alevel_splitters_gui.py
```

The splitter GUI lists installed local paper sets from `data/raw_papers/`. You can select one paper, multiple subjects, or year ranges, then export compact image question/MS assets. The CLI equivalent is `python tools\splitters\alevel\cie\cie_alevel_splitters_cli.py split-downloaded`; use `--paper-key` for a single installed paper set, `--subject` for subjects, `--start-year` / `--end-year` for year ranges, and `--workers` for parallel local processing. By default the splitter writes image and JSON sidecars under `data/processed_questions/`; TXT sidecars are not generated. New QP sidecars include a `content` text field extracted from the PDF question region, with OCR fallback when PDF text is empty or garbled. MS sidecars intentionally omit `content` fields. Each sidecar records the exact source PDF URL once at top level. To upgrade existing QP sidecars, run `python tools\splitters\alevel\cie\cie_alevel_splitters_cli.py backfill-content`.

Package splitter JSON sidecars into one SQLite database per subject:

```powershell
.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\a_level\cie --qualification a_level --exam-board cie --course-code 9231 --dry-run
.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\a_level\cie --qualification a_level --exam-board cie --course-code 9231
```

The generated file name is lowercase snake_case, for example
`data/databases/a_level/cie/cie_a_level_9231.sqlite`. The packer regenerates a
compact runtime database with paper stems, local question keys, searchable
question text, exact QP/MS source URLs, and the crop coordinates needed to
recreate question images from downloaded PDFs.

Run the packer GUI:

```powershell
.venv\Scripts\python tools\packers\packer_gui.py
```

Run the dependency-light smoke tests:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv\Scripts\python -m pytest tools\downloaders\alevel\cie\tests
.venv\Scripts\python -m pytest tools\splitters\alevel\cie\tests
.venv\Scripts\python -m pytest tools\downloaders\admissions\uat\tests
.venv\Scripts\python -m pytest tools\splitters\admissions\uat\tests
.venv\Scripts\python -m pytest tools\packers\tests
```
