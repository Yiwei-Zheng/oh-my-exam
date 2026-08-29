# Architecture

## Overview

Oh-My-Exam is a feature-first modular monolith with sibling browser and server
applications. It uses one versioned HTTP boundary and one hosted PostgreSQL
source of truth. Processing code belongs to the backend but remains independent
of HTTP and GUI frameworks.

```text
Browser
  -> Caddy
      -> frontend static files
      -> /api/v1/* -> FastAPI
                       -> PostgreSQL
                       -> object store
                       -> Redis -> Celery workers -> pipeline core
```

## Repository

```text
oh-my-exam/
├── frontend/
├── backend/
│   ├── config/
│   ├── resources/
│   ├── migrations/
│   ├── scripts/
│   ├── src/oh_my_exam/
│   ├── data/
│   └── tests/
├── assets/
├── tmp/
├── docs/
├── scripts/
├── deploy/
├── .env.example
├── .gitignore
├── AGENTS.md
└── README.md
```

`assets/` contains maintained cross-application design assets. `tmp/` is
untrusted scratch space and no product behavior may depend on it. `scripts/`
contains only repository-wide development and verification entry points.
`deploy/` contains Linux native service and reverse-proxy assets.

## Frontend

The frontend uses a pragmatic Feature-Sliced Design:

```text
src/
├── app/       # router, providers, i18n, global styles
├── pages/     # route composition
├── widgets/   # question tree, document viewer, pipeline console
├── features/  # user actions and workflows
├── entities/  # exam, paper, question, answer, pipeline run
└── shared/    # API client, UI wrappers, utilities, configuration
```

Pages compose features and widgets. Entities do not import features or pages.
Business modules do not import Element Plus directly; `shared/ui/` owns the
component-library boundary. Pinia owns client state. TanStack Vue Query owns
server state. The OpenAPI document generates HTTP request and response types.

## Backend

```text
src/oh_my_exam/
├── main.py
├── api/                 # HTTP adapters and versioned routes
├── modules/
│   ├── identity/
│   ├── catalog/
│   ├── documents/
│   ├── pipeline/
│   ├── administration/
│   ├── audit/
│   └── learning/
├── pipelines/
│   ├── engine/          # step contracts and orchestration
│   └── adapters/        # CIE, PAT, STEP, UAT implementations
├── infrastructure/
│   ├── database/
│   ├── object_store/
│   ├── queue/
│   └── security/
└── shared/
```

Each module owns its application services, domain rules, persistence models,
and API schemas. Route handlers perform authentication, request validation, and
response mapping only. Celery tasks call the same application services as CLI
or administrative adapters. Pipeline core code does not import FastAPI, Celery,
Vue, or an interactive console.

## Dependency direction

```text
requirements
  -> module contracts
      -> application services
          -> domain and pipeline core
              <- infrastructure adapters
      <- HTTP, worker, CLI adapters
```

Forbidden dependencies:

- Frontend source importing backend or Python internals.
- API routes implementing processing or catalog business rules.
- Pipeline core importing FastAPI, Celery, GUI frameworks, or browser concepts.
- Source adapters writing directly into published catalog tables.
- Browser code receiving or constructing filesystem paths or upstream URLs.
- Redis, object storage, retrieval providers, or model providers becoming the
  authority for users, permissions, catalog identity, or publication state.

## Persistence

One PostgreSQL database uses logical schemas:

- `identity`: users, roles, role assignments, and sessions.
- `catalog`: exams, subjects, papers, questions, answers, text, tags, and
  catalog releases.
- `documents`: immutable document identity, versions, and page regions.
- `pipeline`: runs, steps, artifacts, source observations, and configuration
  snapshots.
- `learning`: attempts, progress, and later marking records.
- `audit`: administrator and security events.

Tables follow third normal form unless a documented read model is introduced.
Database changes use Alembic. Internal relations use bigint primary keys. Public
APIs use UUID public ids and stable business keys.

The object store contains immutable PDFs addressed by storage keys derived from
document identity, not user input. PostgreSQL stores checksums, MIME type, byte
size, version, provenance, and the storage key. Production APIs resolve public
ids to objects after authorization.

## Catalog releases

Processing writes staging artifacts and normalized candidate records. Validation
checks schemas, relationships, document existence, page bounds, crop rectangles,
and representative rendering. A successful release is immutable and is made
active by switching one release reference transactionally. A failed build does
not mutate the active release.

Corrections are append-only revisions. Saving a correction activates it
immediately. Rollback activates a previous revision or release; it does not
restore legacy repository code.

## Document delivery

Full-paper endpoints support HTTP byte ranges. Question and answer endpoints
resolve normalized regions and produce clipped vector PDFs with cache validators.
PDF.js renders both forms in the frontend. Extracted answer text is delivered by
a separate JSON endpoint. Permanent JPG crops are forbidden; thumbnails are
bounded caches only.

## Deployment

Linux bare-metal deployment uses Caddy, systemd, a Python virtual environment,
a static frontend build, FastAPI, Celery, PostgreSQL, and Redis. Native and
development modes share the same typed environment settings. Missing required
production settings fail at startup. Docker-specific files and paths are not
part of this architecture iteration.

## References

- FastAPI multi-file applications:
  https://fastapi.tiangolo.com/tutorial/bigger-applications/
- PostgreSQL schemas:
  https://www.postgresql.org/docs/current/ddl-schemas.html
- SQLAlchemy 2 ORM:
  https://docs.sqlalchemy.org/en/20/orm/
- Alembic migrations:
  https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Celery workflows and workers:
  https://docs.celeryq.dev/en/stable/userguide/
- Feature-Sliced Design:
  https://fsd.how/docs/reference/slices-segments/
- Caddy frontend and API proxy pattern:
  https://caddyserver.com/docs/caddyfile/patterns
- PDF.js:
  https://mozilla.github.io/pdf.js/getting_started/
