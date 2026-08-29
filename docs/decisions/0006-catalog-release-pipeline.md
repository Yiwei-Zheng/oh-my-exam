# 0006: Durable pipeline runs and catalog releases

## Status

Accepted on 2026-08-29.

## Context

Downloading, splitting, text extraction, linking, classification, packaging,
and publication are long-running operations. They must survive browser
disconnects and worker restarts. Publishing partial output directly into the
active catalog would expose inconsistent questions.

## Decision

Represent processing as durable runs with explicit step and artifact records:

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

Steps are idempotent and resumable. Different subjects may run concurrently,
initially with a global concurrency limit of two. Publication is serialized.
FastAPI creates and controls runs; Celery workers execute them; PostgreSQL is
the authoritative source for run state. Redis is transport infrastructure, not
the authoritative job database.

Each successful build creates an immutable catalog release. Deterministic
validation runs automatically. A passing release becomes active immediately;
there is no manual review gate. A failing release leaves the previous active
release unchanged. Rollback switches the active release pointer.

Answer extraction initially stores only raw extracted text and normalized
Markdown. Marking-point structures are deferred. Extraction failure does not
block question publication when the authoritative answer PDF remains usable.

Administrator corrections create revisions and become active immediately.
Previous revisions remain available for rollback and audit.

## Consequences

- Web requests never run a complete pipeline inline.
- Pipeline logs are streamed to the browser with Server-Sent Events.
- Portable SQLite databases become exports of a selected release, not the
  hosted source of truth.
- A worker crash marks work interrupted and allows resumption from the latest
  successful step.

## References

- Celery 5.6 user guide and workflow documentation:
  https://docs.celeryq.dev/en/stable/userguide/
- PostgreSQL schemas:
  https://www.postgresql.org/docs/current/ddl-schemas.html
- Alembic migration environments:
  https://alembic.sqlalchemy.org/en/latest/tutorial.html
