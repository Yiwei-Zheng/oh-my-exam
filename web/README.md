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

## Question document delivery

The browser fetches question and mark-scheme extracts from the backend by exam
and question ids:

```text
GET /api/v1/exams/{exam_id}/questions/{question_id}/question.pdf
GET /api/v1/exams/{exam_id}/questions/{question_id}/answer.pdf
```

The backend looks up the server-owned source PDF and stored crop metadata, then
returns one vector PDF page per crop region. The response is intended for inline
display and uses a private one-hour browser cache. Missing catalog records,
source papers, or crop regions return `404`; invalid crop metadata returns
`422`.

Vector extracts are the default for born-digital papers because they preserve
text and formula quality without transferring the entire paper. A future image
fallback should use a compressed format such as WebP for scanned papers, where
a clipped PDF can still embed a full-page raster image. When a workflow reads
many questions from one paper, the existing full-paper endpoint plus byte-range
requests and session caching may use less total bandwidth than many independent
extracts.
