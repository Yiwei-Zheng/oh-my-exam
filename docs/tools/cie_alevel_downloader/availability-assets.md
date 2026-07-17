# CIE A-Level Availability Assets

## Scope

Per-subject Frank availability files used by the CIE A-Level downloader.

## What belongs here

- Availability file path.
- Required top-level fields.
- Coverage and merge rules.
- GUI download-selection behavior.

## What does not belong here

- Downloader launcher details.
- Manifest component-rule schema.
- Raw PDF output layout.
- Splitter output formats.

## Related docs

- `docs/tools/cie_alevel_downloader/overview.md`
- `docs/tools/cie_alevel_downloader/manifest.md`
- `docs/modules/resources-and-configs.md`

## Path

```text
resources/exam_boards/cie/available_assets/{qualification}/{subject_code}.json
```

Example:

```text
resources/exam_boards/cie/available_assets/a_level/9709.json
```

## Meaning

Availability files list assets actually returned by Frank listing endpoints.

They are more specific than manifests. A manifest may overestimate possible files; availability files should contain files the source listed as downloadable.

## Required Fields

- `source`: upstream source base URL.
- `generated_at`: write time.
- `coverage`: subject/year/season ranges represented by the file.
- `assets`: downloadable QP/MS assets.

## Coverage Rule

Coverage controls whether the file is sufficient for a selected request.

An asset list for `9701` covering `2010-2019` is not enough for a later `2002-2009` request.

## Merge Rule

- Sniffing a new range merges new assets into the subject file.
- Existing assets should be preserved.
- Coverage metadata should record the sniffed range and failed query count.

## GUI Rule

- If sniffing is disabled, download only matching assets already listed locally.
- If sniffing is enabled, sniff the selected subjects and year range first, then download matching listed assets.
