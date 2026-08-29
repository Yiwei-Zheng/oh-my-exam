# Product Requirements

## Product goal

Oh-My-Exam is a bilingual web product for finding, viewing, teaching, and
processing exam questions. It supports students, teachers, and administrators.
The initial catalog includes CIE A-Level, PAT, STEP, ENGAA, and NSAA, and the
architecture must allow new exam families without global rewrites.

## Product surfaces

- The maintained client is a responsive Vue 3 web application.
- Students and teachers browse published questions and their source documents.
- Administrators use the same application to manage accounts, inspect catalog
  data, run processing pipelines, correct metadata, and monitor publication.
- Native mobile and desktop applications are out of scope.

## Accounts and access

- Accounts use email and password authentication.
- Roles are student, teacher, and administrator.
- Public registration is disabled until a later requirement enables it.
- Bootstrap administrator credentials come from deployment configuration.
- Bootstrap creates the first administrator only; authenticated administrators
  can create additional administrator, teacher, and student accounts.
- Passwords use a memory-hard password hash and are never stored in plaintext.
- New managed accounts require at least 15 password characters. Login attempts
  are limited independently by normalized account and client IP.
- Browser authentication uses secure HttpOnly cookies; credentials and bearer
  tokens are not stored in frontend source or local storage.
- Source PDFs are protected resources. The browser receives internal document
  ids, never filesystem paths, object keys, or upstream source URLs.

## Question browser

- The canonical hierarchy is qualification, provider or exam board, exam or
  subject, year, session, paper, question, and subquestion.
- Knowledge point, syllabus section, question type, difficulty, and processing
  state are filters and tags rather than competing tree roots.
- Tree nodes load lazily and large question lists use cursor pagination.
- Search supports printed question text, identity fields, and normalized tags.
- Deep links preserve the selected node, filters, document view, and page.
- A paper can be opened as a complete PDF.
- A question can be opened as a dynamically clipped vector PDF.
- An answer can be viewed as a clipped PDF, within its complete source PDF, and
  as extracted raw text or normalized Markdown.
- If answer text extraction fails, the authoritative PDF remains available and
  the question may still be published.

## Processing and publication

- Administrators can discover, download, validate, split, extract text or OCR,
  link questions and answers, classify, package, and publish from the web UI.
- Web requests create durable job records and start the pipeline in an isolated
  subprocess; they do not execute processing inside the request handler.
- Every step has explicit inputs, outputs, status, logs, and artifact identity.
- Steps are idempotent and retryable. A failed run keeps its logs and may be
  restarted by an administrator.
- The current release serializes publication. Distributed workers and
  cross-host resumption are future scale-out capabilities.
- Each build produces an isolated candidate catalog.
- Deterministic validation runs automatically. A passing release becomes active
  without manual review; a failing release leaves the previous release active.
- Administrator corrections create append-only revisions and become active
  immediately. A rollback UI is future work.
- Structured marking points are out of scope for the current iteration.

## Data and storage

- The supported self-hosted release uses separate normalized SQLite databases
  for identity and job state, the active catalog, and portable pipeline inputs.
- PostgreSQL is the documented scale-out direction, not a runtime dependency of
  this release. A future migration must preserve API and module boundaries.
- Original PDF documents are immutable, checksummed, versioned server objects.
- The local object store lives under `backend/data/objects/`; the storage API
  remains replaceable by an S3-compatible implementation.
- Permanent question and answer JPG derivatives are not part of the new data
  model. Temporary thumbnails are caches with retention limits.
- Generated artifacts retain enough provenance to reproduce and audit a release.

## Web experience

- The interface is Apple-inspired, based on restrained macOS document-workspace
  patterns rather than copied Apple assets or a generic dashboard theme.
- Desktop uses adaptive navigation, tree, and preview columns. Tablet collapses
  navigation. Phone uses drill-down routes.
- The document rail switches between question PDF, answer PDF, structured text,
  and source paper while retaining question context.
- Light, dark, and follow-system themes are supported.
- Chinese and English use the same i18n system. All user-visible interface text
  belongs in translation resources.
- Layouts remain operable from 320px phones through desktop screens, in portrait
  and landscape, without page-level horizontal overflow.
- Primary interactions are keyboard accessible, have visible focus, provide at
  least 44px touch targets, meet WCAG AA contrast, and respect reduced motion.

## Deployment

- Production supports current Ubuntu and Debian releases with systemd.
- Caddy serves the frontend and proxies versioned API requests.
- FastAPI runs under systemd. Pipeline subprocesses are created by the backend
  and their durable state remains in SQLite.
- Installation, migration, upgrade, backup, and health-check procedures must be
  repeatable and documented.
- Docker support is explicitly out of scope for the current iteration.
- Windows remains a development target, not a supported production target.

## Future capabilities

AI tutoring, automatic marking, progress tracking, paper generation, retrieval,
and deterministic mathematical tools remain product goals. They must use stable
question and document citations and must not replace authoritative catalog data.
