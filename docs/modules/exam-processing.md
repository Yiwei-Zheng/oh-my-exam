# Exam Processing Module

## Scope

Cross-tool boundaries for exam paper processing.

## What belongs here

- Processing phases.
- Dependency rules between tool types.
- Shared expectations that are not tied to one exam board.

## What does not belong here

- CIE-specific endpoints.
- Subject-specific cutter rules.
- GUI or CLI command syntax.
- Tool-owned data schemas.

## Related docs

- `docs/architecture.md`
- `docs/modules/resources-and-configs.md`
- `docs/modules/local-data-storage.md`
- `docs/tools/cie_alevel_downloader/overview.md`
- `docs/tools/cie_alevel_splitter/overview.md`
- `docs/tools/cie_alevel_classifier/overview.md`

## Phases

1. Download raw exam assets.
2. Split raw papers into question-level assets.
3. Classify and tag questions.
4. Store normalized question-bank data.
5. Package data for client import or distribution.

## Boundary Rules

- Each phase must expose a callable core service.
- GUI and CLI must call the same core service.
- A later phase may consume files or public metadata from an earlier phase.
- A later phase must not import private implementation modules from an earlier phase.
- Packers may consume splitter JSON sidecars and images as public processed output, but must not import splitter internals.
- Tools may duplicate small model definitions when hard runtime decoupling is more important than sharing.
- Shared helper packages may be used for stable source identifiers such as
  remote URL construction when that avoids cross-importing tool internals.

## Failure Rules

- Processing tools should report failures explicitly.
- A tool must not silently produce misleading outputs when boundaries or source data cannot be trusted.
- Runtime reports belong under `data/reports/`.
