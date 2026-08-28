# Official Web

## Scope

`web/frontend/` owns the bilingual responsive browser client. Its sibling
`web/backend/` owns the hosted API. The frontend consumes backend capabilities
only through versioned HTTP APIs.

## Current state

The previous React website and browser-side SQLite, OCR, matching, PDF rendering,
and source-URL proxy implementation have been removed. The repository currently
contains an intentionally empty Vue application environment; no replacement
product page or business workflow is implemented yet.

The backend exposes question-level PDF routes at
`/api/v1/exams/{exam_id}/questions/{question_id}/{question|answer}.pdf`. The
server resolves the source paper by internal catalog identity and returns only
the recorded crop regions as a compact vector PDF. Clients do not receive an
upstream URL or need to download the complete source paper to display one
question. The full-paper endpoint remains available for explicit source-paper
viewing.

## Toolchain

- Vue 3 with TypeScript and Vite.
- Vue Router for URL boundaries.
- Pinia for client-only state.
- Vue I18n for Chinese and English resources.
- Vitest, Vue Test Utils, ESLint, vue-tsc, and Prettier for quality checks.
- Vite proxies `/api` to `http://127.0.0.1:8000` by default. Override the target
  with `VITE_API_PROXY_TARGET`.

Dependencies install into `web/frontend/node_modules/`. The project `.npmrc`
places npm cache under `web/frontend/.npm-cache/`; global package installation is
not part of the workflow. `.node-version` pins the expected Node runtime.

## Boundaries

- `App.vue` is an application shell, not a business-logic container.
- Routes belong under `src/router/`.
- Client state belongs under `src/stores/`.
- All user-visible text must come from `src/i18n/` resources.
- Future product code should be grouped by feature.
- Frontend modules must not import backend or Python tool internals.
- The browser must not connect directly to PostgreSQL, object storage, retrieval,
  or model providers.

## Verification

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`
