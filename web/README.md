# Web applications

The web product is split into sibling applications:

- `frontend/`: browser UI and browser-only adapters.
- `backend/`: hosted API, business services, and persistence adapters.

The frontend calls the backend through versioned HTTP APIs. Neither application
imports the other's internal code, and production may deploy them together or
separately without changing this source boundary.

The frontend environment uses Vue 3, TypeScript, and Vite. The old React product
code has been removed; replacement product pages are intentionally not part of
the environment setup.
