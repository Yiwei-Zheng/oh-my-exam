# Official Web

## Scope

`web/frontend/` owns the bilingual browser client. `web/backend/` owns the
hosted API, identity store, administrator services, and update-job orchestration.
The deployable web product must not require repository-root `tools/` at runtime.

## Current state

The former promotional WebGL homepage has been removed. The root route now
directs users to an email/password login. Registration is closed. Authenticated
administrators can access a responsive control desk with user totals, seven-day
active users, role counts, a fourteen-day activity chart, a hierarchical
question catalog, and question-update job state.

Passwords use Argon2. The server sends a signed, HttpOnly, same-site session
cookie; the frontend does not store bearer tokens. Administrator routes enforce
the role in both the Vue navigation guard and FastAPI dependencies. The server
remains the authoritative security boundary.

The update endpoint starts at most one job and persists its state. A deployment
command packaged with `web/` performs source checking, downloading, splitting,
cataloging, and classification. The browser only starts the job and polls its
status. If the command is absent, the interface explains the missing
configuration and does not simulate success.

## Toolchain

- Vue 3, Vue Router, Pinia, and Vue I18n.
- Element Plus for accessible form, tree, feedback, and progress primitives.
- ECharts for the activity time series, loaded with the administrator route.
- FastAPI, Argon2, and PyJWT on the backend.
- Vitest, ESLint, vue-tsc, Prettier, and Pytest for verification.

## Boundaries

- Frontend features call only versioned HTTP APIs.
- Credentials, source URLs, download logic, and processing commands never enter
  browser code.
- The update command is an argument array and is never passed through a shell.
- User-visible text belongs in the Chinese/English i18n resources.
- Production hosting rewrites browser routes to `index.html` and serves the API
  under the same site or an explicitly allowed CORS origin.

## Verification

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`
- `python -m pytest web/backend/tests`
