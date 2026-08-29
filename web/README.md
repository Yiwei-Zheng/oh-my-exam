# Web applications

The web product is split into sibling applications:

- `frontend/`: browser UI and browser-only adapters.
- `backend/`: hosted API, business services, and persistence adapters.

The frontend calls the backend through versioned HTTP APIs. Neither application
imports the other's internal code, and production may deploy them together or
separately without changing this source boundary.

## Cross-platform start

`web/start.py` starts the already prepared web application. FastAPI
serves both the versioned API and the compiled Vue frontend from one origin, so
production does not run the Vite development server or embed a deployment
domain. The same script supports Windows, macOS, and Linux.

The script is intentionally decoupled from environment setup: it does not create
a virtual environment, install dependencies, modify configuration, or build the
frontend. The active Python environment must already contain the backend
dependencies, and `web/frontend/dist/index.html` must already exist.

Start from the repository root:

```powershell
# Windows
python web\start.py
```

```bash
# macOS or Linux
python3 web/start.py
```

The default listener is `0.0.0.0:8000`; override it with `--host`, `--port`,
`HOST`, or `PORT`. Add `--check` to validate the prepared runtime without
starting the server.

The frontend uses Vue 3, TypeScript, Vite, Element Plus, and ECharts. It provides
a bilingual email/password login and an administrator workspace. Public
registration is disabled.

## Authentication bootstrap

The backend stores users and activity in `web/backend/data/application.sqlite3`
by default. On the first start, provide `OME_BOOTSTRAP_ADMIN_EMAIL` and
`OME_BOOTSTRAP_ADMIN_PASSWORD`; the password is Argon2-hashed and the account is
only inserted when the email does not already exist. Set `OME_JWT_SECRET` in
production and enable HTTPS cookies with `OME_SECURE_COOKIES=true`.

## Question update command

The administrator update button is enabled when
`OME_QUESTION_UPDATE_COMMAND_JSON` contains a JSON string array for a command
packaged with the deployed `web/` artifact. The backend invokes it without a
shell and allows only one job at a time. The command may report progress as one
JSON object per stdout line:

```json
{"stage":"splitting","progress":62,"message":"Splitting new CIE papers"}
```

Valid stages are `checking`, `downloading`, `splitting`, `cataloging`, and
`classifying`. Without this deployment command the button remains visible but
disabled instead of pretending that an update ran.

## Question document delivery

The browser fetches question and mark-scheme extracts from the backend by exam
and question ids:

```text
GET /api/v1/exams/{exam_id}/questions/{question_id}/question.pdf
GET /api/v1/exams/{exam_id}/questions/{question_id}/answer.pdf
```

The backend looks up the server-owned source PDF and stored crop metadata, then
returns one vector PDF page per crop region. The response is intended for inline
display and uses a private one-hour browser cache. Missing catalog records,
source papers, or crop regions return `404`; invalid crop metadata returns
`422`.

Vector extracts are the default for born-digital papers because they preserve
text and formula quality without transferring the entire paper. A future image
fallback should use a compressed format such as WebP for scanned papers, where
a clipped PDF can still embed a full-page raster image. When a workflow reads
many questions from one paper, the existing full-paper endpoint plus byte-range
requests and session caching may use less total bandwidth than many independent
extracts.

The local backend reads `data/databases/global_exam_catalog.sqlite` by default.
Override it with `OME_DATABASE_PATH`. Document rows contain relative storage
keys under `OME_PAPER_ROOT`; public or third-party file URLs are not stored.
