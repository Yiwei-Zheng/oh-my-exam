# Promotional Homepage

## Scope

Create the first production-ready promotional surface for the Vue website. This
task does not implement product search, authentication, registration, analytics,
or backend integration.

## Experience

- `/` presents a single-screen bilingual hero with no product CTA.
- The first visit in a browser session plays a skippable, silent typographic
  intro. Later visits enter the hero directly, while a replay control remains
  available.
- The intro reduces `OH-MY-EXAM` to its leading `O`; that letter follows a curved
  path into the hero, fills into a dark core, and reveals the event horizon at the
  same position.
- Desktop uses a left visual / right copy layout. Narrow screens center and soften
  the black hole behind foreground copy.
- The headline cycles through four fixed English statements. The event horizon
  uses deterministic, academically valid English formulas and code fragments.
- Light mode uses a warm editorial surface; dark mode uses a graphite surface.
  Initial theme and language follow the browser, and manual choices persist.
- The event horizon uses a large upper-left to lower-right accretion plane.
  Academic characters flow consistently along fixed paths rather than rotating
  the complete composition.

## Interaction and accessibility

- Continuous motion pauses automatically in hidden tabs; no visible pause control
  is shown on this promotional surface.
- `prefers-reduced-motion` skips the intro and displays a static composition.
- Primary controls use native buttons, visible focus states, localized labels,
  and at least 44 px targets.
- Language selection uses a keyboard-operable globe menu. Theme switching uses
  an interruptible transform-only circular reveal and avoids full-page snapshots.
- The page remains operable from 320 px upward in portrait and landscape without
  horizontal overflow.
- Unknown routes show a themed, localized 404 page and a route back to `/`.

## Implementation boundaries

- Use a dynamically imported PixiJS WebGL renderer with a runtime glyph atlas and
  merged meshes. Keep a static SVG fallback for reduced motion and browsers
  without WebGL2.
- Self-host Space Grotesk for display text and IBM Plex Mono for academic
  characters under their bundled SIL Open Font Licenses.
- Do not ship the visual references from `tmp/index/` as production assets.
- Do not add analytics code, cookies, external scripts, audio, or a favicon.

## Verification

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`
- Visual checks at desktop and phone widths in both themes, including reduced
  motion and a short landscape viewport.
