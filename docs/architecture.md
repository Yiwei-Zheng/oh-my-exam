# Architecture

## Scope

Stable repository-level architecture for Oh-My-Exam.

## What belongs here

- Project goal.
- Top-level module boundaries.
- Dependency direction.
- Forbidden coupling.
- Top-level directory responsibilities.

## What does not belong here

- Exam-board details.
- Subject-specific rules.
- Downloader, splitter, classifier, GUI, or CLI implementation details.
- Data format schemas owned by one tool.
- Task history.

## Related docs

- `docs/principles.md`
- `docs/requirements.md`
- `docs/modules/exam-processing.md`
- `docs/modules/resources-and-configs.md`
- `docs/modules/local-data-storage.md`
- `docs/modules/global-question-catalog.md`
- `docs/modules/official-web.md`
- `docs/tools/cie_alevel_downloader/overview.md`
- `docs/tools/cie_alevel_splitter/overview.md`
- `docs/tools/metadata_packer/overview.md`

## Project Goal

Oh-My-Exam is a hosted, multi-user exam question search, tutoring, marking, and
paper-generation project. Its initial product focus is admissions tests,
especially ENGAA, NSAA, TMUA, and STEP.

The repository must support multiple exam types, exam boards, subjects, and
tools without forcing their details into global documents or shared code.
Local processing remains supported, but the hosted service is the authority for
user state and published catalog data.

## Top-Level Boundaries

- `tools/`: local processing tools, grouped by responsibility, qualification, and exam board.
- `tools/shared/`: small tool-neutral helper packages used by multiple local tools.
- `tools/packers/`: local packers that convert processed public metadata into portable subject databases.
- `web/backend/`: hosted API, service adapters, and future multi-user application persistence.
- `configs/`: source-controlled configuration and manifests.
- `resources/`: source-controlled external metadata and reference resources.
- `data/`: runtime output and local generated state.
- `docs/`: agent-facing project documentation.
- `requirements/`: separate production backend, development backend, and data-processing
  installation entry points for the shared root Python environment.
- `scripts/setup_env.py`: operating-system-neutral environment bootstrap entry point.
- `web/`: web product boundary containing sibling frontend and backend applications.
- `web/frontend/`: primary browser client and official website for desktop and mobile browsers. Its framework is an implementation choice, not a backend boundary.
- `temp/`: user scratch input only. Project code must not depend on it.
- `tmp/`: temporary local runtime files.

## Dependency Direction

- Product requirements constrain architecture.
- Architecture constrains modules.
- Modules constrain tools.
- Tools may read configs, resources, and data formats documented under their own docs.
- GUI and CLI are adapters over core services.
- Core services must not depend on GUI frameworks.

## Module Boundaries

- Downloaders collect raw source assets.
- Splitters process local raw assets into question-level outputs.
- Shared tool helper packages may contain source URL construction or other
  dependency-neutral utilities, but not downloader or splitter workflow logic.
- Classifiers/taggers annotate processed questions.
- Storage code persists normalized local data.
- Packers convert processed question metadata into compact per-subject import
  databases and a normalized global SQLite catalog. Catalogs store server-owned
  document storage keys, never third-party source URLs.
- The server reads the normalized global catalog and must not import downloader
  or splitter internals.
- Clients consume versioned HTTP APIs and must not import server or Python tool internals.
- Portable SQLite packages remain valid import/export and optional offline assets;
  they are not the hosted multi-user source of truth.
- The website uses the server API for catalog search and all hosted product
  capabilities. Portable SQLite packages cross the server import/export boundary,
  not the browser runtime boundary.
- OCR, matching, and PDF crop replay must remain standalone services rather than
  Vue component logic if those capabilities are reintroduced.

## Forbidden Coupling

- Downloader code must not import splitter internals.
- Splitter code must not import downloader internals.
- GUI code must not implement core business logic.
- Core code must not import GUI libraries or read user input.
- Subject lists, component rules, and external catalog data must not be hard-coded in UI code.
- Runtime output must not be treated as source configuration.
- Website code must not import Python tool internals or open portable subject
  databases directly. It consumes versioned server APIs.
- Website code must not connect directly to the hosted database, object store,
  RAGFlow, or model providers.
- RAGFlow and language models must not become authoritative stores for exam data,
  permissions, user state, or citations.
- Python packages share the repository-root `.venv/`. Dependency entry points
  remain separated under `requirements/` for backend and data processing.
- A virtual environment is recreated on each target operating system; `.venv/`
  is never copied between Windows and Linux.
- No scripts, source files, or project docs may be placed inside `.venv/`.

## Directory Responsibilities

- `tools/downloaders/{qualification}/{exam_board}/`: downloader packages and launchers.
- `tools/splitters/{qualification}/{exam_board}/`: splitter packages and launchers.
- `tools/packers/`: packer packages and launchers that consume public processed metadata.
- `tools/shared/`: source-level helper packages that preserve downloader/splitter decoupling.
- `tools/classifiers/{qualification}/{exam_board}/`: classifier/tagging tools.
- `resources/exam_boards/{exam_board}/`: board-specific source metadata, catalog snapshots, syllabus references, and availability files.
- `configs/`: maintained manifests and configuration files.
- `data/raw_papers/`: downloaded raw papers.
- `data/processed_questions/`: generated question-level outputs.
- `data/reports/`: runtime reports.
- `data/databases/`: generated per-subject SQLite import databases and
  `global_exam_catalog.sqlite`.
- `data/*.sqlite3`: local databases.
- `requirements/backend.txt`: production backend installation entry point.
- `requirements/backend-dev.txt`: editable backend and backend-test installation entry point.
- `requirements/data-processing.txt`: local data tool, GUI, OCR, and test
  installation entry point.
- `web/backend/`: versioned hosted API and adapters for catalog, identity, paper
  storage, retrieval, language models, and deterministic math tools.
- `web/frontend/`: bilingual responsive marketing and local question-search surface. It
  owns browser adapters and presentation services, while reusable source
  processing remains under `tools/` and hosted business logic remains under
  `web/backend/`. It is the maintained end-user client for phone, tablet, and desktop.
- `web/frontend/` and `web/backend/` are sibling applications. Neither is nested
  inside or imported by the other; deployment topology does not change this
  source boundary.

## Hosted Runtime Direction

- Start as a modular monolith rather than independent business microservices.
- PostgreSQL will own normalized published catalog data, users, attempts,
  progress, conversations, citations, and usage records.
- Original PDFs are server-owned assets behind a `PaperStore` boundary. Local
  filesystem storage is supported for development; production targets an
  S3-compatible object store.
- Catalog document rows store a path-independent storage key. API requests
  identify questions and papers by internal ids; the server must never accept a
  client-supplied file path or upstream URL.
- Normal question display requests identify a question and document side through
  the versioned API. The server resolves the original paper and replays stored
  crop regions into a question-level vector PDF; crop calculation remains a
  backend service rather than browser or route-handler logic.
- Born-digital papers use vector extracts by default. Scanned papers may use a
  compressed raster fallback when clipping would retain the full source-page
  image. Explicit full-paper viewing remains a separate endpoint and may use
  byte-range requests and session caching.
- RAGFlow is a replaceable retrieval adapter. DeepSeek is a replaceable model
  adapter. Both are called only from the server.
- Mathematical tools run through typed, restricted contracts in an isolated
  execution environment. Model-generated arbitrary code is not executed.
