# Metadata Packer

## Scope

Packer for converting splitter JSON sidecars into one SQLite database per subject.

## What belongs here

- Packer package boundary.
- CLI and GUI launchers.
- Per-subject SQLite ownership.
- Stable table responsibilities.

## What does not belong here

- Splitter boundary detection.
- Downloader source discovery.
- Classifier and tagging schemas.
- Client import format details.

## Related docs

- `docs/architecture.md`
- `docs/requirements.md`
- `docs/modules/exam-processing.md`
- `docs/modules/local-data-storage.md`
- `docs/tools/cie_alevel_splitter/processed-question-layout.md`
- `docs/tools/cie_alevel_splitter/crop-regions.md`
- `docs/tools/metadata_packer/cie_alevel_database_schema.md`

## Package Boundary

- Root: `tools/packers/`.
- Core package: `tools/packers/src/exam_packer/`.
- CLI launcher: `python tools/packers/packer_cli.py ...`.
- GUI launcher: `python tools/packers/packer_gui.py`.

The packer consumes splitter JSON metadata as public file output. It must not
import splitter internals. For CIE A-Level, it assumes the unified splitter
schema documented under `docs/tools/cie_alevel_splitter/` and does not maintain
compatibility branches for older sidecar formats.

The packer also recognizes processed UAT admissions sidecars under
`data/processed_questions/uat/admissions/{engaa|nsaa}/`. Their official PDF URL
is read from each crop region's `source_pdf` field. In the GUI these appear as
`Admissions Tests` → `UAT` → `ENGAA` or `NSAA`.

## Database Output

The packer writes one SQLite database per subject:

```text
data/databases/{qualification}/{exam_board}/{exam_board}_{qualification}_{course_code}.sqlite
```

Example:

```text
data/databases/a_level/cie/cie_a_level_9231.sqlite
```

The database file already identifies `exam_board`, `qualification`, and
`course_code`, so the subject database does not create `qualifications`,
`exam_boards`, or `courses` tables.

## Core Tables

The detailed CIE A-Level subject database schema is defined in
`docs/tools/metadata_packer/cie_alevel_database_schema.md`.

The subject database owns these core tables:

- `database_info`
- `papers`
- `questions`
- `crop_regions`
- `question_texts`

The subject database must not create `schema_migrations` or FTS5 shadow tables.

`papers` stores QP/MS source stems and the exact downloadable URL for each
document. Runtime code must use the stored URLs because not every provider URL
can be reconstructed from a stem.

`questions` stores only the paper link, local question key, and human-readable
question number. Search text from QP metadata is stored in `question_texts`,
whose `question_id` is `questions.id`. MS metadata must not include `content`,
`content_source`, or `content_warning`; a sidecar that includes those fields is
not valid CIE A-Level splitter metadata.

`crop_regions` is structured as one row per source segment. It keeps only the
PDF rectangle, source side (`0` for QP, `1` for MS), render DPI, join gap, and
optional post-render crop pixels needed to recreate the question image from a
downloaded PDF.

## CLI

Dry-run scan:

```powershell
.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\a_level\cie --qualification a_level --exam-board cie --course-code 9231 --dry-run
```

Write or update a subject database:

```powershell
.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\a_level\cie --qualification a_level --exam-board cie --course-code 9231
```

Rebuild from scratch:

```powershell
.venv\Scripts\python tools\packers\packer_cli.py --metadata-root data\processed_questions --output-dir data\databases\a_level\cie --qualification a_level --exam-board cie --course-code 9231 --overwrite
```

The packer writes a regenerated compact subject database. `--overwrite` keeps
the same external behavior for callers that explicitly request a rebuild, but
the generated schema itself is always refreshed before records are inserted.

## GUI

Run the local GUI:

```powershell
.venv\Scripts\python tools\packers\packer_gui.py
```

The GUI automatically scans the metadata directory at startup and lists only
courses that contain packable JSON sidecars. It does not mix the downloadable
resource catalog or empty subject directories into the local processed-paper
catalog.
Select `qualification`, then `exam_board`, then `course_code`; these fields are
cascading dropdowns, not free-text inputs. The output directory is derived from
the selected qualification and exam board, such as `data/databases/a_level/cie`.
Use the scan button after changing the metadata root or when local processing
has produced more sidecars. The scan status reports the number of packable
courses and metadata files. The packer scans and reads only the selected course
when packing.
