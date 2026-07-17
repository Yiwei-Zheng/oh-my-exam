# Local Data Storage Module

## Scope

Runtime data and local persistence boundaries.

## What belongs here

- Responsibilities of `data/`.
- Local-first storage rules.
- Database ownership at a high level.

## What does not belong here

- Full database schema.
- Tool-specific output schemas.
- Source-controlled config or resource rules.
- GUI preferences implementation details beyond storage ownership.

## Related docs

- `docs/architecture.md`
- `docs/requirements.md`
- `docs/decisions/0001-exam-pipeline-local-sqlite.md`
- `docs/tools/cie_alevel_splitter/processed-question-layout.md`

## `data/`

- Runtime output.
- Local generated state.
- Not source configuration.

## Current Data Areas

- `data/raw_papers/`: downloaded source PDFs.
- `data/processed_questions/`: generated question-level assets.
- `data/reports/`: tool reports and status logs.
- `data/gui/`: local GUI preferences.
- `data/databases/`: generated per-subject SQLite databases for import or distribution.
- `data/*.sqlite3`: local SQLite databases.

## Database Rule

- SQLite is the local database default.
- Do not require a global database service for local processing.
- Schema changes must be upgradeable through migrations.
- Schema design must remain normalized.
