# Data Migration

## Scope

Migrate the existing application SQLite database, global and subject catalogs,
original PDFs, crop metadata, answer text, configuration, and source resources
into the new backend boundary. The existing corpus is treated as authoritative
until reconciliation completes.

## Method

1. Inventory source paths, counts, byte sizes, database schemas, and storage keys.
2. Create database backups and a SHA-256 manifest for retained documents.
3. Import identity and catalog records into PostgreSQL staging schemas.
4. Move immutable PDFs into `backend/data/objects/` without changing document
   identity; verify every retained checksum.
5. Validate relationships, pages, regions, answer text, and representative PDF
   rendering.
6. Run one complete pipeline and verify automatic release activation.
7. Switch all code and configuration to the new paths and perform a cold start.
8. Delete authorized legacy code and derived data only after the complete gate.

## Deletion

The accepted clean break removes old roots, launchers, Flet GUIs, permanent JPG
crops, duplicate processed reports, and fully imported sidecars. It retains
original PDFs, migrated data, backups, checksums, migration manifests,
corrections, releases, and audit records.

Deletion commands must resolve and verify exact workspace paths before acting.
No deletion targets an environment variable, glob, repository root, or parent
directory.
