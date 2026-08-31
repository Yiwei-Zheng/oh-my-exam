# Product Requirements

## Product goal

Oh-My-Exam is a bilingual web product for finding, viewing, teaching, and
processing exam questions. It supports students, teachers, and administrators.
The initial catalog includes CIE A-Level, PAT, STEP, ENGAA, and NSAA, and the
architecture must allow new exam families without global rewrites.

## Product surfaces

- The maintained client is a responsive Next.js web application using the
  shadcn preset `b27I38wi` (Rhea, neutral base, blue theme, Figtree and
  Hugeicons) as its design language.
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
- Catalog metadata, search, question images, and source PDFs require an active
  authenticated session. Only health checks, login, and invitation registration
  are public API endpoints.
- Source PDFs are protected resources. The browser receives internal document
  ids, never filesystem paths, object keys, or upstream source URLs.

## Question browser

- The canonical hierarchy is qualification, provider or exam board, exam or
  subject, year, session, paper, question, and subquestion.
- Knowledge point and syllabus section filters use their own searchable tree;
  question type, difficulty, and processing state remain tags and filters rather
  than competing roots in the paper tree.
- Tree nodes load lazily and large question lists use cursor pagination.
- Search supports printed question text, identity fields, normalized tags, and
  syllabus knowledge points.
- Image search accepts a camera photo, selected image, drag-and-drop image, or
  image pasted from the clipboard. The server extracts text with a replaceable
  OCR adapter, ranks catalog questions by overlapping terms, and returns at most
  the top five matches.
- Deep links preserve the selected node, filters, document view, and page.
- A paper can be opened as a complete PDF.
- Clicking a question opens a focused modal document viewer instead of adding an
  inline preview below the result list. The viewer loads only the catalog-owned
  pre-rendered JPG and reports a missing asset instead of rendering or embedding a PDF.
- An answer can be viewed as a pre-rendered JPG and as extracted raw text or normalized Markdown.
- If answer text extraction fails, the authoritative PDF remains available and
  the question may still be published.

## Processing and publication

- Administrators can discover, download, validate, split, extract text or OCR,
  link questions and answers, classify, package, and publish from the web UI.
- The question-bank update page lists only subjects with an end-to-end workflow.
  Administrators select subjects with grouped tree checkboxes, probe fixed upstream sources, compare the
  result with local immutable PDFs, confirm newly discovered resources, and set
  pipeline parallelism before processing begins. Parallelism defaults to the
  server's logical processor count and is bounded from 1 to 32.
- Probe, download, split, inventory, and search publication are individually
  runnable from the workflow track. Each stage offers incremental update and
  overwrite modes; the same modes are available for the complete pipeline.
- Web requests create durable job records and start the pipeline in an isolated
  subprocess; source probing also runs as a durable background job so slow
  upstream sites never hold the Web request open.
- Every running operation can be paused and resumed from the update page.
  Source probing pauses at the next subject boundary; subprocess-backed stages
  suspend and resume the complete process tree without restarting the stage.
- Request failures, partial probe failures, and failed background jobs open a
  localized dialog that identifies the stage, explains the likely cause,
  suggests a recovery action, and keeps raw technical details available.
- The subprocess boundary uses UTF-8 explicitly. Running jobs report the current
  stage and resource, elapsed time, and an estimated remaining duration.
- Network-heavy source discovery and downloads start conservatively, increase
  concurrency after sustained success, and reduce it with server-directed
  cooldowns after HTTP 429 or 503 responses.
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
- Every preprocessing adapter writes question and answer JPGs before packaging.
  Published catalogs contain only questions whose required pre-rendered images
  exist and match their recorded artifact metadata; request-time PDF cropping is prohibited.
- Generated artifacts retain enough provenance to reproduce and audit a release.

## Web experience

- The interface follows the shared shadcn preset while retaining restrained,
  document-workspace information density instead of a generic KPI dashboard.
- Desktop uses adaptive navigation, tree, and preview columns. Tablet collapses
  navigation. Phone uses drill-down routes.
- Administrator paper assets use the canonical collapsible tree rather than a
  flattened paper list. Filtering preserves matching nodes and their ancestors.
- Exam-program paper and question totals appear as aligned columns inside the
  paper tree; there is no duplicate exam-program inventory widget beside it.
- The administrator overview samples host CPU, RAM and disk use every two
  seconds while visible. Project storage separates code, databases, papers and
  other runtime data.
- The question modal switches between the protected question paper, answer paper,
  and structured text while retaining question context.
- Light, dark, and follow-system themes are supported.
- Chinese and English use the same i18n system. All user-visible interface text
  belongs in translation resources.
- Layouts remain operable from 320px phones through desktop screens, in portrait
  and landscape, without page-level horizontal overflow.
- Primary interactions are keyboard accessible, have visible focus, provide at
  least 44px touch targets, meet WCAG AA contrast, and respect reduced motion.
- Loading, navigation, disclosure and press states use interruptible,
  non-linear motion with immediate pointer feedback.

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
