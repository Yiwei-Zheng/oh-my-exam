# Official Web

## Scope

`web/frontend/` owns the bilingual responsive browser client. Its sibling
`web/backend/` owns the hosted API. The frontend consumes backend capabilities
only through versioned HTTP APIs.

## Current state

The previous React website and browser-side SQLite, OCR, matching, PDF rendering,
and source-URL proxy implementation have been removed. The Vue application now
contains a bilingual promotional homepage and branded not-found page. The
homepage is intentionally a product statement rather than an application entry:
it does not expose registration, authentication, search, marking, or other
unfinished workflows. The long-term requirement for a clear question-search
entry remains outstanding until that workflow is implemented.

The homepage supports system-aware light and dark themes, persistent language and
theme preferences, an accessible globe language menu, an optional session intro,
reduced-motion fallbacks, and a keyboard-accessible intro replay control.
Theme changes use an interruptible transform-only circular reveal without
full-page transition snapshots. Its event-horizon artwork uses a dynamically
loaded PixiJS WebGL renderer with a runtime glyph atlas and merged geometry;
three character streams bend into the accretion plane while a static SVG remains
available for reduced-motion and unsupported browsers. Hidden tabs pause motion
automatically; the visible pause control has been removed.
The GPU scene uses an astrophotographic composition rather than a schematic
ring: an asymmetric orange-white accretion disk and gravitational lens surround
an inclined dark core while a dense perspective sheet of academic glyphs bends
toward it.

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
- PixiJS for the lazily loaded homepage WebGL artwork.
- Vitest, Vue Test Utils, ESLint, vue-tsc, and Prettier for quality checks.
- Vite proxies `/api` to `http://127.0.0.1:8000` by default. Override the target
  with `VITE_API_PROXY_TARGET`.
- Production hosting must rewrite unknown browser paths to `index.html` so Vue
  Router can render the branded not-found route on direct visits.

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
- Analytics is disabled. If a provider is selected later, integrate it behind a
  provider-neutral boundary in the application shell only after its event model,
  consent requirements, data retention, and privacy documentation are approved.
  Do not place provider calls inside feature components.
- Brand, hero, and academic orbit copy intentionally remains English across both
  locales and is centralized under `src/i18n/invariantContent.ts`.

## Verification

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`
