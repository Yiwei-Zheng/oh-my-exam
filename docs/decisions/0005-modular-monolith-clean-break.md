# 0005: Modular monolith and clean-break repository

## Status

Accepted on 2026-08-29.

## Context

The repository currently separates processing tools under `tools/` and the web
product under `web/`. Runtime data is rooted at `data/`. This makes the hosted
application, administrator workflows, processing packages, configuration, and
data ownership appear as separate products even though they form one system.

The maintained product is a bilingual web application. Administrators must be
able to run the complete acquisition and publication pipeline from the browser.
Students and teachers use the same API and document browser with role-specific
permissions.

## Decision

Use a feature-first modular monolith with two deployable source applications:

```text
frontend/
backend/
```

The backend owns accounts, catalog metadata, source PDFs, processing pipelines,
portable database export, and audit records. Pipeline core code remains usable
without HTTP or GUI dependencies. FastAPI routes and Celery tasks are adapters
over the same application services.

Use a clean-break migration:

- Do not preserve legacy command wrappers, import paths, or dual directory
  layouts after the new system passes its acceptance gate.
- Use Git history to recover tracked legacy code rather than compatibility code.
- Preserve authoritative runtime data through database backup, object checksums,
  catalog releases, and migration manifests.
- Delete derived question JPG files after dynamic PDF preview is verified.

The repository root may also contain `assets/`, `tmp/`, `docs/`, `scripts/`,
deployment configuration, `.env.example`, `.gitignore`, `AGENTS.md`, and
`README.md`.

## Consequences

- The current `web/`, `tools/`, `configs/`, `resources/`, `requirements/`, and
  root `data/` boundaries will disappear.
- Source-specific code moves under `backend/src/oh_my_exam/pipelines/adapters/`.
- Default exam configuration and reference resources move under `backend/`.
- Existing commands and documentation change at the cutover.
- Migration must be staged in small commits while the final state contains no
  legacy compatibility layer.

## References

- FastAPI, "Bigger Applications - Multiple Files":
  https://fastapi.tiangolo.com/tutorial/bigger-applications/
- Feature-Sliced Design, "Slices and segments":
  https://fsd.how/docs/reference/slices-segments/
