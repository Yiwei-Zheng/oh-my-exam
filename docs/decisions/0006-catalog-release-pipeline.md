# 0006: Durable pipeline runs and catalog releases

## Status

Accepted on 2026-08-29.

## Context

Downloading, splitting, text extraction, linking, classification, packaging,
and publication are long-running operations. They must continue after browser
disconnects. Publishing partial output directly into the active catalog would
expose inconsistent questions.

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

Steps are idempotent and retryable. FastAPI records runs in the application
SQLite database and launches the packaged release command as an isolated local
subprocess. The command emits structured progress for the administrator UI.
Publication is serialized by constructing one candidate catalog at a time.
Distributed execution is not part of this release.

Each build creates a temporary candidate database. Deterministic validation
runs automatically. A passing candidate atomically replaces the active catalog;
there is no manual review gate. A failing candidate leaves the previous active
catalog unchanged. Catalog-release history and rollback are future work.

Answer extraction initially stores only raw extracted text and normalized
Markdown. Marking-point structures are deferred. Extraction failure does not
block question publication when the authoritative answer PDF remains usable.

Administrator corrections create revisions and become active immediately.
Previous revisions remain available for rollback and audit.

## Consequences

- Web requests never run a complete pipeline inline.
- Pipeline logs are streamed to the browser with Server-Sent Events.
- Portable SQLite databases remain pipeline inputs; the active normalized
  catalog is the published query source.
- An API restart can interrupt a local subprocess. The durable run remains
  inspectable and the administrator can retry it.

## References

- Python subprocess management:
  https://docs.python.org/3/library/subprocess.html
- SQLite atomic commit:
  https://sqlite.org/atomiccommit.html
