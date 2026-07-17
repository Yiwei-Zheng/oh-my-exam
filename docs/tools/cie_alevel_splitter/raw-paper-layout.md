# CIE A-Level Raw Paper Layout

## Scope

Raw PDF layout consumed by the CIE A-Level splitter.

## What belongs here

- Raw paper path convention.
- Required source identity.
- Legacy layout note.

## What does not belong here

- Downloader workflow.
- Processed question output layout.
- Crop region schema.
- Subject-specific cutter internals.

## Related docs

- `docs/tools/cie_alevel_downloader/overview.md`
- `docs/tools/cie_alevel_splitter/overview.md`
- `docs/tools/cie_alevel_splitter/processed-question-layout.md`

## Current Layout

```text
data/raw_papers/{exam_board}/{qualification}/{subject_code}/{year}/{session}/{stem}.pdf
```

Example:

```text
data/raw_papers/cie/a_level/9709/2024/w24/9709_w24_qp_12.pdf
```

## Metadata

PDF-adjacent metadata may store source information such as `subject_name`.

For CIE A-Level, `subject_name` should use stable Cambridge-style English names rather than mirror-localized names.

## Legacy Layout

Older files may exist under:

```text
data/raw_papers/{exam_board}/{qualification}/{subject_code}/{session}/{stem}.pdf
```

Use the downloader migration command before relying on old folders in new processing.
