# CIE A-Level Downloader

## Scope

CIE A-Level downloader package and workflow.

## What belongs here

- Downloader package boundary.
- Launchers.
- Cambridge catalog sync.
- Frank availability discovery.
- Polite PDF downloading.
- Raw layout migration.
- Downloader concurrency.

## What does not belong here

- Splitter implementation.
- Question cutting rules.
- Processed question output schema.
- Global architecture rules.

## Related docs

- `docs/architecture.md`
- `docs/modules/exam-processing.md`
- `docs/modules/resources-and-configs.md`
- `docs/tools/cie_alevel_downloader/availability-assets.md`
- `docs/tools/cie_alevel_downloader/manifest.md`
- `docs/tools/cie_alevel_splitter/raw-paper-layout.md`

## Package Boundary

- Root: `tools/downloaders/alevel/cie/`.
- Implementation package: `tools/downloaders/alevel/cie/src/cie_alevel_downloader/`.
- GUI launcher: `python tools/downloaders/alevel/cie/cie_alevel_downloader_gui.py`.
- CLI launcher: `python tools/downloaders/alevel/cie/cie_alevel_downloader_cli.py ...`.
- Installed entry point: `ome-cie-alevel-downloader`.

The downloader owns manifest parsing, Cambridge catalog sync, Frank availability discovery, polite downloading, raw layout migration, GUI, and CLI.

It must not import splitter modules.

## Workflow

1. Load subject and component candidates from manifests.
2. Load existing per-subject availability files.
3. Optionally sniff Frank listing endpoints for selected subjects and years.
4. Merge newly discovered assets into availability files.
5. Download only listed assets.
6. Write raw PDFs under `data/raw_papers/`.
7. Leave splitting to the splitter phase.

URL probing is a fallback for debugging. It must not be the default high-volume workflow.

## Frank Source Adapter

Frank listing endpoints:

- `POST https://cie.fraft.cn/obj/Common/Subject/combo`
- `POST https://cie.fraft.cn/obj/Common/Fetch/renum`

`renum` fields:

- `subject`: syllabus code, such as `9709`.
- `year`: full year, such as `2024`.
- `season`: `Mar`, `Jun`, or `Nov`.

The returned file list is the source of truth for downloadable Frank assets.

Skip combined mark schemes such as `ms_1+2+...pdf`.

## Cambridge Catalog Sync

The sync command reads Cambridge AS & A Level subject pages and writes:

- `resources/exam_boards/cie/cie_a_level_subjects_official.json`
- `resources/exam_boards/cie/cie_a_level_subject_rules.json`

Run from the repository root:

```powershell
.venv\Scripts\python tools\downloaders\alevel\cie\sync_cambridge_catalog.py
```

The official catalog is authoritative for current subject names and codes, not a complete historical archive.

## GUI Behavior

- User selects subjects, years, document types, output paths, delay, and workers.
- Without manual sniffing, the GUI downloads only assets already present in availability files.
- With manual sniffing, the GUI refreshes selected subject/year coverage before downloading.
- Completion percentage compares local raw PDFs with selected available assets.
- GUI strings must remain bilingual.

## Polite Crawling

- Respect configured delay after each download attempt.
- Treat HTTP 429 as a stop signal.
- Preserve resumable `.part` downloads.
- Keep Frank/CIE worker counts modest.

## Concurrency

- `max_workers=1` preserves sequential crawling.
- Higher values run multiple attempts in parallel.
- Each worker still respects the configured delay.
- The downloader keeps a bounded number of in-flight futures.

## Raw Layout Migration

Current raw PDFs use:

```text
data/raw_papers/{exam_board}/{qualification}/{subject_code}/{year}/{session}/{stem}.pdf
```

Legacy files may exist at:

```text
data/raw_papers/{exam_board}/{qualification}/{subject_code}/{session}/{stem}.pdf
```

The CLI exposes `migrate-raw-layout` for migration.
