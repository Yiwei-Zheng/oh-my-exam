# CIE A-Level Downloader Manifest

## Scope

Subject and component candidate manifests for the CIE A-Level downloader.

## What belongs here

- Manifest ownership.
- Component rule model.
- Cambridge-derived subject rules.
- Compatibility with old flat component lists.

## What does not belong here

- Frank availability file schema.
- Raw PDF output layout.
- Splitter behavior.
- GUI workflow details.

## Related docs

- `docs/tools/cie_alevel_downloader/overview.md`
- `docs/tools/cie_alevel_downloader/availability-assets.md`
- `docs/modules/resources-and-configs.md`

## Paths

- `configs/cie_a_level_manifest.json`
- `configs/cie_a_level_through_2025_manifest.json`
- `resources/exam_boards/cie/cie_a_level_subject_rules.json`
- `resources/exam_boards/cie/cie_a_level_subjects_official.json`

## Rule Model

Use `component_rules` for year-bounded component candidates:

```json
{
  "valid_from": 2002,
  "valid_to": 2019,
  "components": ["1", "2", "3", "4", "5", "6", "7"]
}
```

The downloader expands only rules valid for each exam session year.

## Compatibility

The loader may support legacy flat `components` lists.

New or regenerated manifests should prefer `component_rules`.

## Cambridge-Derived Rules

- Generated rules come from Cambridge official AS & A Level subject pages and syllabus overview pages.
- The generated rules are conservative candidates.
- They may need subject-specific refinement from syllabus PDFs and short Frank trials before high-volume downloading.

## Known CIE Rules

- Subject component codes can change by syllabus year.
- Early CIE files may use single-digit components.
- Modern CIE files often use two-digit components.
- Combined mark schemes such as `ms_1+2+3+4+5+6+7` must not be downloaded.
