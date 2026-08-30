# 0012: On-demand JPG question preview

## Status

Accepted on 2026-08-30.

## Context

Question-level vector PDFs add a PDF viewer and document chrome where the user
needs a compact, responsive question image. Restoring a permanent crop corpus
would duplicate immutable source content and complicate corrections.

## Decision

Render ordered question and answer regions from the immutable source PDF into a
single vertically joined JPG response. The renderer uses normalized crop
coordinates and does not persist the derivative. Full source papers remain PDF
responses.

Question-level routes end in `.jpg` and return `image/jpeg` with private cache
headers. Frontends display the result as a responsive image and keep source PDF
access as a separate operation.

## Consequences

- Question previews need no embedded PDF viewer.
- Crop corrections take effect without rebuilding a derivative corpus.
- Text selection is unavailable in the image preview; structured extracted text
  remains a separate view.
- Source PDFs remain the authoritative protected artifacts.
