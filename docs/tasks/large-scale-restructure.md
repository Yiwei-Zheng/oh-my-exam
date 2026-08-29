# Large-scale repository restructure

## Goal

Migrate Oh-My-Exam to sibling `frontend/` and `backend/` applications. Move all
exam acquisition, processing, catalog packaging, account persistence, original
PDF ownership, and administration pipelines into the backend boundary. Deliver
an Apple-inspired web document browser and Linux bare-metal deployment.

## Confirmed constraints

- Use a modular monolith, SQLite-backed self-hosted runtime, filesystem storage
  boundary, Vue 3, and versioned REST APIs. Preserve seams for later scale-out.
- Keep pipeline core independent of FastAPI and GUI code.
- Use automatic validation and publication without a manual review gate.
- Store answer raw text and Markdown; defer marking-point structures.
- Render question and answer views dynamically from source PDFs.
- Delete permanent processed-question JPGs after the acceptance gate.
- Use a clean break: no legacy wrapper commands, imports, paths, or dual writes.
- Support Linux bare-metal deployment. Do not implement Docker support now.
- Preserve the user's existing uncommitted `.gitignore` change.

## Target repository

```text
frontend/
backend/
assets/
tmp/
docs/
scripts/
deploy/
.env.example
.gitignore
AGENTS.md
README.md
```

## Migration phases

1. Commit architecture and decision records.
2. Move the frontend and backend source applications.
3. Consolidate processing packages, configuration, resources, requirements, and
   tests under `backend/`; update every import and entry point.
4. Normalize and migrate the identity, run-state, portable input, and active
   catalog SQLite databases with count and relationship reports.
5. Move original PDFs and retained runtime data into `backend/data/`; preserve
   path-independent document keys and generate a checksum manifest.
6. Implement durable pipeline runs, automatic release validation/publication,
   lazy catalog APIs, document preview APIs, and immediate correction revisions.
7. Implement the Apple-inspired adaptive browser and administrator pipeline UI.
8. Verify the clean-cut gate, then remove legacy directories, JPG derivatives,
   duplicate reports, and fully imported sidecars.
9. Verify Linux native install and systemd restart behavior.

## Clean-cut acceptance gate

- Identity and catalog entity counts reconcile.
- Retained PDFs match the source SHA-256 manifest.
- All document regions refer to valid pages and rectangles.
- Representative question and answer PDFs render for CIE 9709, PAT, STEP, and
  UAT exam families.
- One complete 9709 pipeline run reaches an automatically active release.
- Authentication, authorization, lazy tree browsing, filtering, search, source
  PDF, question PDF, answer PDF, and structured answer text pass end-to-end.
- Backend tests and migrations pass.
- Frontend unit tests, type check, lint, build, accessibility checks, and E2E
  tests pass at phone, tablet, and desktop breakpoints.
- Linux native installation and systemd recovery pass.
- A cold start succeeds with no dependency on old repository paths.

## Deletion authorization

After every acceptance condition passes, remove the old `web/`, `tools/`,
`data/`, `configs/`, `resources/`, and `requirements/` roots, old launchers and
Flet GUIs, processed-question JPGs, duplicate report output, and fully imported
sidecars. Do not remove original PDFs, migrated catalog data, corrections,
database backups, checksums, migration manifests, or audit records.

## Remaining risks

- The runtime corpus is about 5.66 GiB and contains more than 130,000 files.
- Existing storage keys and hard-coded root paths must be migrated without
  silently changing document identity.
- The local subprocess executor is single-host. Multi-host processing will need
  an explicit queue and database migration rather than compatibility shims.
- Source PDF availability and licensing must remain controlled by authenticated
  document endpoints.
