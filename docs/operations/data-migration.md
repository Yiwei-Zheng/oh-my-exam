# Data Migration Record

## Completed clean break

- Maintained Vue source moved from `web/frontend` to `frontend`.
- FastAPI source moved from `web/backend` to `backend`.
- Downloader, splitter and packer packages moved from `tools` into `backend/src/oh_my_exam/pipelines`.
- Tracked exam configuration and resources moved below `backend`.
- `data/{databases,processed_questions,raw_papers,reports}` moved to `backend/data` on the same volume.
- The active catalog gained `answer_versions.raw_text`; the empty `marking_points` table was removed.
- Permanent JPGs below `backend/data/processed_questions` were removed after dynamic PDF preview passed API and browser verification.

Original PDFs, JSON crop metadata, portable databases and reports were retained. Legacy import names and launch wrappers are not supported.

## Verification

The migration gate checks backend tests, all new CLI entry points, SQLite integrity, frontend lint/typecheck/tests/build, authenticated tree browsing, question list loading, dynamic PDF delivery and narrow-screen overflow. A failed catalog candidate never replaces the active catalog.
