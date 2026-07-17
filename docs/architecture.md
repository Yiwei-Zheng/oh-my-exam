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
- `docs/modules/official-web.md`
- `docs/tools/cie_alevel_downloader/overview.md`
- `docs/tools/cie_alevel_splitter/overview.md`
- `docs/tools/metadata_packer/overview.md`

## Project Goal

Oh-My-Exam is a local-first exam question search, marking, and paper-generation project.

The repository must support multiple exam types, exam boards, subjects, and tools without forcing their details into global documents or shared code.

## Top-Level Boundaries

- `tools/`: local processing tools, grouped by responsibility, qualification, and exam board.
- `tools/shared/`: small tool-neutral helper packages used by multiple local tools.
- `tools/packers/`: local packers that convert processed public metadata into portable subject databases.
- `configs/`: source-controlled configuration and manifests.
- `resources/`: source-controlled external metadata and reference resources.
- `data/`: runtime output and local generated state.
- `docs/`: agent-facing project documentation.
- `web/`: primary React/Vite end-user client, official website, and local-first question-search surface for desktop and mobile browsers.
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
- Packers convert processed question metadata into compact per-subject runtime databases for search and PDF recropping, including exact per-document source URLs.
- Clients consume public interfaces or portable subject packages, not Python tool internals.
- The website may load a selected portable subject SQLite package in a Web Worker.
  OCR, matching, and PDF crop replay stay in standalone client services rather
  than React components. A replaceable HTTP API remains the boundary for future
  hosted search, accounts, marking, and protected data.

## Forbidden Coupling

- Downloader code must not import splitter internals.
- Splitter code must not import downloader internals.
- GUI code must not implement core business logic.
- Core code must not import GUI libraries or read user input.
- Subject lists, component rules, and external catalog data must not be hard-coded in UI code.
- Runtime output must not be treated as source configuration.
- Website code must not import Python tool internals. It may consume documented,
  portable per-subject database packages through the runtime asset boundary.
- No scripts, source files, or project docs may be placed in `.venv/` or `tools/.venv/`.

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
- `data/databases/`: generated per-subject SQLite databases.
- `data/*.sqlite3`: local databases.
- `web/`: bilingual responsive marketing and local question-search surface. It
  owns browser adapters and client-side search services, while reusable source
  processing remains under `tools/`. It is the maintained end-user client for
  phone, tablet, and desktop form factors.
