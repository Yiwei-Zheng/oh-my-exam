# Exam Processing

## Responsibility

The processing module owns durable acquisition and publication workflows. It
coordinates source adapters and reusable steps without placing exam-specific
rules in global services.

## Standard workflow

```text
discover
  -> download
  -> validate-source
  -> split
  -> extract-text-or-ocr
  -> link-question-answer
  -> classify
  -> validate-catalog
  -> package
  -> publish
```

Each step declares input artifacts, output artifacts, idempotency identity,
progress, logs, and failure state. A run stores its resolved configuration
snapshot. Retrying a successful step must not duplicate authoritative records.

## Reproducible exam adapters

Every maintained exam family must expose its complete processing path as
source-controlled CLI code. Manual database edits and undocumented one-off AI
transformations are not accepted pipeline steps. A reproducible adapter includes
source discovery/download, deterministic naming, question and answer splitting,
answer pairing validation, portable database packaging, classification, catalog
validation and publication.

TMUA is the reference admissions implementation. `backend/scripts/process_tmua.py`
composes the UAT downloader, geometry/OCR splitter, official answer-key validator,
portable packer and atomic global release. Re-running it after UAT-UK publishes
another archive paper processes existing inputs idempotently and adds only newly
discovered material. Runtime PDFs, crops, reports and SQLite files remain private
under `backend/data`; reconstruction logic, topic catalogs and tests remain in
source control.

## Adapter boundary

Adapters may define source discovery, naming, catalog interpretation, and
PDF-layout rules. They implement pipeline contracts and are tested with fixed
fixtures. Adapters do not publish directly and do not import FastAPI or runtime
executor adapters.

Configuration uses source-controlled defaults below `backend/config/exams/`.
Browser input selects supported operations; it cannot upload or execute
arbitrary Python.

## Failure and publication

Missing assets, unsupported layouts, OCR failures, and invalid regions are
explicit outcomes. Failed work remains inspectable and resumable. Catalog
validation is automatic. Passing releases activate immediately; failed releases
leave the current active release unchanged.

## Runtime adapters

FastAPI creates, reports, and authenticates runs. Before creation, an
administrator may probe the fixed sources for one or more workflow-ready
subjects and compare discovered resource identities with local files. A
backend-owned subprocess receives the selected subject ids and bounded worker
count, executes acquisition through publication, and writes structured
progress; SQLite owns run history. The browser polls durable state and is never
the owner of execution. A queue or Server-Sent Events may replace polling later
without changing pipeline contracts.
