# 0013: Pre-rendered question and answer images

## Status

Accepted on 2026-08-30.

## Context

Request-time PDF cropping made preview correctness depend on a second renderer
path and exposed font-encoding defects in older Further Mathematics papers.
Every maintained splitter already has the authoritative geometry and can render
the final image while it validates the crop.

## Decision

All exam adapters render question and answer JPGs during preprocessing. Portable
subject databases record image keys relative to `processed_questions`; the global
catalog publishes those keys through normalized `question_images` rows. A release
is rejected unless every question and linked answer has its corresponding image.

Question image API routes read these immutable derivatives directly. They do not
fall back to cropping source PDFs. Full source PDFs and crop coordinates remain
available as authoritative source material and provenance.

Unreliable PDF text containing control characters, private-use glyphs, unexpected
scripts, or known symbol-font mojibake is rejected instead of being published as
question or answer text. The image remains the authoritative readable view.

## Consequences

- Preview rendering is deterministic and does not consume PDF-rendering CPU per request.
- Crop changes require preprocessing and a new catalog release.
- The image corpus is now a required backup and deployment input alongside PDFs and databases.
- Older portable catalogs must be rebuilt from their splitter outputs before release.
