# 0007: Immutable PDF storage and dynamic question preview

## Status

Accepted on 2026-08-29.

## Context

The corpus contains original question and answer PDFs, crop metadata, derived
question JPG files, and portable databases. Permanent JPG derivatives duplicate
several gigabytes of data and make source corrections expensive.

## Decision

Original documents are immutable objects identified by an internal document id,
version, SHA-256 checksum, and path-independent storage key. Identical content
is deduplicated. Local and bare-metal deployments store objects below
`backend/data/objects/`; the storage interface remains compatible with a future
S3-compatible implementation.

Question and answer previews are rendered from the original PDF and normalized
page regions. Normal question display returns a clipped vector PDF. The browser
uses PDF.js for full-paper and question-level viewing. Temporary thumbnails may
be generated below `backend/data/cache/` and removed by retention policy, but
they are not catalog assets.

The browser never receives a filesystem path, storage key, or upstream source
URL. It uses versioned endpoints addressed by public ids. Full-paper responses
support byte-range requests; question and answer responses use cache validators.

After migration counts, checksums, region bounds, and representative rendering
tests pass, existing processed-question JPG files and duplicate report images
are deleted. JSON sidecars are deleted only after their authoritative content is
verified in the migrated database and migration manifest.

## Consequences

- Crop coordinates and document identity become authoritative data.
- Correcting a crop does not require replacing an image corpus.
- Original PDFs, catalog releases, corrections, database backups, and migration
  manifests remain protected assets.

## References

- Amazon S3 object key model:
  https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-keys.html
- PDF.js viewer and display layers:
  https://mozilla.github.io/pdf.js/getting_started/
