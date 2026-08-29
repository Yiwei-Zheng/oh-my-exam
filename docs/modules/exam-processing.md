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

## Adapter boundary

Adapters may define source discovery, naming, catalog interpretation, and
PDF-layout rules. They implement pipeline contracts and are tested with fixed
fixtures. Adapters do not publish directly and do not import FastAPI or Celery.

Configuration uses source-controlled defaults below `backend/config/exams/`
and versioned administrator overrides in PostgreSQL. Browser input cannot upload
or execute arbitrary Python.

## Failure and publication

Missing assets, unsupported layouts, OCR failures, and invalid regions are
explicit outcomes. Failed work remains inspectable and resumable. Catalog
validation is automatic. Passing releases activate immediately; failed releases
leave the current active release unchanged.

## Runtime adapters

FastAPI creates, cancels, retries, and reports runs. Celery executes steps. Redis
transports work. PostgreSQL owns run history. Server-Sent Events deliver progress
without making the browser the owner of execution state.
