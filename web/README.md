# Web applications

The web product is split into sibling applications:

- `frontend/`: browser UI and browser-only adapters.
- `backend/`: hosted API, business services, and persistence adapters.

The frontend calls the backend through versioned HTTP APIs. Neither application
imports the other's internal code, and production may deploy them together or
separately without changing this source boundary.

The current frontend uses React/Vite. A future framework rewrite should preserve
the same API boundary and remain separate from backend business logic.
