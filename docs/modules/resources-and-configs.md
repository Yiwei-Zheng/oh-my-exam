# Resources And Configs Module

## Scope

Source-controlled configuration and external reference resources.

## What belongs here

- Responsibilities of `configs/`.
- Responsibilities of `resources/`.
- Rules for catalog snapshots, manifests, syllabi, and availability metadata.

## What does not belong here

- Runtime outputs under `data/`.
- Tool command details.
- Full JSON schema for a tool-owned format.
- Subject-specific cutter implementation rules.

## Related docs

- `docs/architecture.md`
- `docs/modules/exam-processing.md`
- `docs/tools/cie_alevel_downloader/manifest.md`
- `docs/tools/cie_alevel_downloader/availability-assets.md`

## `configs/`

- Contains maintained manifests and configuration.
- Source-controlled.
- Code should read config files instead of hard-coding subject lists or component rules.
- Config files should be independent from implementation modules.

## `resources/`

- Contains source-controlled external metadata and references.
- Exam-board resources live under `resources/exam_boards/{exam_board}/`.
- Future exam boards should use sibling directories.
- Syllabus files belong under the relevant exam-board resource tree.
- Availability files may live here when they are source-controlled discovery metadata.

## Exam Board And Source Identity

- The canonical exam-board key owns the first directory segment under
  `data/raw_papers/` and `data/processed_questions/`, and the exam-board segment
  under `data/databases/{qualification}/`.
- A mirror or archive site is a downloader implementation detail, not an exam
  board. Remote URLs may be used transiently to download files, but catalog
  databases must retain only the local server-owned storage key.
- Current admissions mappings are PAT → `pearson_vue`, STEP → `ocr`, and
  ENGAA/NSAA → `uat`.

## `temp/`

- Scratch input only.
- No project code may depend on `temp/`.
- Useful files from `temp/` must be moved into `resources/`, `configs/`, or another proper source location before use.
