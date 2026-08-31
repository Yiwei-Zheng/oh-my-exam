# Architecture

## System shape

Oh-My-Exam is a modular monolith with a browser client and a server application separated by `/api/v1`. The frontend never imports backend code. FastAPI owns authentication, catalog reads and corrections, PDF delivery and pipeline job control. Pipeline modules also expose CLI entry points and do not depend on the GUI.

API access is default-deny: only health, login, and invitation registration are
public. The development launcher exposes Next.js to the LAN while FastAPI stays
on loopback and is reached through the frontend proxy.

```text
Browser -> Caddy -> Next.js web server
                 -> /api/v1 -> FastAPI
                               -> backend/data/application.sqlite3
                               -> backend/data/databases/global_exam_catalog.sqlite
                               -> backend/data/raw_papers
                               -> isolated pipeline subprocess
```

The current self-hosted release uses separate SQLite databases for identity/job
state and the normalized question catalog. Both live below `backend/data`;
portable subject databases are pipeline inputs. A future scale-out design may
adopt PostgreSQL, but it is not a runtime dependency or accepted migration in
this release.

## Repository

```text
oh-my-exam/
├── frontend/                 # Next.js, React, shadcn, i18n and browser adapters
├── backend/
│   ├── config/exams/         # maintained pipeline configuration
│   ├── resources/            # maintained source catalogs and syllabuses
│   ├── scripts/              # backend migrations and release commands
│   ├── src/oh_my_exam/
│   │   └── pipelines/        # adapters, packaging and release orchestration
│   ├── data/                 # private runtime databases, PDFs and reports
│   └── tests/
├── assets/                   # maintained shared visual assets
├── tmp/                      # disposable scratch space
├── deploy/                   # Caddy and systemd examples
├── docs/
└── scripts/                  # repository-wide environment and start commands
```

`tmp/` is never an application dependency. `backend/data/` is private runtime state and is not committed. Original PDFs are immutable inputs; normalized crop coordinates remain provenance data. Every splitter also writes final question and answer JPGs under `processed_questions`; packaging records their relative storage keys and release validation requires complete image coverage.

## Catalog release

The dedicated Web update page probes fixed upstream sources and compares their
resource identities with local immutable PDFs before an administrator confirms
the download. Probing is recorded and executed in a background thread, while
processing stages run in the backend-owned subprocess. Subject selection,
bounded download concurrency, the requested stage, and update/overwrite mode
are passed through environment variables. Administrators can run download,
split, portable-database inventory, or search publication independently, or run
them in sequence. Incremental mode skips complete local artifacts; overwrite
mode regenerates the selected stage. Publication always builds and validates an
isolated candidate before atomically replacing the active catalog. A failed
candidate leaves the active file untouched.

Answer corrections are append-only `answer_versions` rows with `raw_text` and `markdown`. Saving creates and immediately publishes a new version. Structured marking points are intentionally absent.

## Question browser and documents

The browser uses the hierarchy qualification, exam board, program, year, session, paper and question. Paper nodes fetch question lists on demand. Knowledge points expose a separate `Mathematics / domain / topic` hierarchy backed by syllabus parent ids. The right rail switches between pre-rendered question JPG, pre-rendered answer JPG and structured text. Full source PDFs remain available through authorized internal IDs. On request, the paper-store boundary renders the recorded source page and marks the question or answer regions for in-context viewing. The browser never receives filesystem paths or upstream source URLs.

The authenticated administrator resource endpoint samples host CPU, memory and
disk through `psutil`. Project storage traversal is cached and classifies code,
SQLite databases, immutable papers and other runtime data so two-second UI
polling does not trigger a full filesystem walk on every request.

Text and knowledge-point search query the normalized catalog directly. Image
search sends a bounded browser-normalized data URL to FastAPI, where the OCR
adapter extracts text before catalog matching. OCR is an optional backend
capability and returns an explicit unavailable state when no engine is installed;
the frontend does not perform business matching or call model providers directly.

## Dependency rules

- Frontend code calls HTTP APIs only.
- Route handlers validate/authenticate and call services; processing remains below `pipelines/`.
- Pipeline adapters may share contracts but do not import frontend or FastAPI modules.
- Source adapters do not directly replace the active catalog.
- All user-visible frontend strings use i18n resources.
- A new exam family is an adapter package, not a new root application.

## References

- [FastAPI bigger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
- [Vue application structure](https://vuejs.org/guide/scaling-up/tooling.html)
- [Feature-Sliced Design](https://fsd.how/docs/reference/slices-segments/)
- [SQLite atomic commit](https://sqlite.org/atomiccommit.html)
- [Apple Human Interface Guidelines](https://developer.apple.com/design/human-interface-guidelines/)
- [Caddy common patterns](https://caddyserver.com/docs/caddyfile/patterns)
- [systemd service units](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)
