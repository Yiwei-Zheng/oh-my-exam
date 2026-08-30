# 0011: Next.js and shadcn web client

## Status

Accepted.

## Decision

The maintained browser client uses Next.js App Router and shadcn components.
Its shared design configuration is preset `b27I38wi`: Rhea style, neutral base,
blue theme, Figtree typography, default radius and Hugeicons.

FastAPI remains the only application API. The web client accesses it through
same-origin `/api/v1` requests. In development Next.js rewrites `/api` to the
configured FastAPI process. In production Caddy sends `/api` to FastAPI and all
other traffic to the Next.js server.

## Consequences

- The frontend is built and served as a Node.js process rather than static Vite
  output.
- Authentication continues to use the existing HttpOnly same-origin cookie.
- UI components are repository-owned shadcn source, so product-specific changes
  do not require wrapping a second component framework.
- The former Vue and Element Plus client is removed rather than maintained as a
  parallel presentation stack.
