# CIE A-Level Splitter

## Scope

CIE A-Level splitter package and production cutting rules.

## What belongs here

- Splitter package boundary.
- Launchers.
- Subject-specific cutter structure.
- Generic fallback rule.
- Current 9709 and 9231 support.
- Validation expectations.

## What does not belong here

- Downloader implementation.
- Frank availability workflow.
- Full `crop_regions` schema.
- Global architecture rules.

## Related docs

- `docs/architecture.md`
- `docs/modules/exam-processing.md`
- `docs/tools/cie_alevel_splitter/raw-paper-layout.md`
- `docs/tools/cie_alevel_splitter/processed-question-layout.md`
- `docs/tools/cie_alevel_splitter/crop-regions.md`
- `docs/decisions/0002-subject-specific-pdf-cutters.md`

## Package Boundary

- Root: `tools/splitters/alevel/cie/`.
- Common implementation package: `tools/splitters/alevel/cie/src/common/cie_alevel_splitter/`.
- Subject cutters: `tools/splitters/alevel/cie/src/{subject_code}/`.
- GUI launcher: `python tools/splitters/alevel/cie/cie_alevel_splitters_gui.py`.
- CLI launcher: `python tools/splitters/alevel/cie/cie_alevel_splitters_cli.py ...`.
- Installed entry point: `ome-cie-alevel-splitter`.

The splitter owns local raw corpus discovery, PDF/image splitting, subject-specific cutters, SQLite ingestion, GUI, and CLI.

It must not import downloader modules.

## Workflow

1. Discover downloaded raw PDFs.
2. Select paper sets by subject, year range, or paper key.
3. Dispatch to a subject-specific cutter when available.
4. Fall back to the generic splitter only when no production cutter exists.
5. Extract visible question text for question-paper sidecars.
6. Write question images and JSON sidecars.
7. Write reports under `data/reports/`.

Existing sidecars can be upgraded with:

```powershell
python tools\splitters\alevel\cie\cie_alevel_splitters_cli.py backfill-content
```

## Cutter Rules

- Production cutters should use PDF metadata, text spans, words, drawings, images, page geometry, rotation, and raster connected components.
- OCR is not the primary boundary detector.
- All CIE A-Level cutters must emit the unified JSON sidecar schema defined in
  `processed-question-layout.md` and `crop-regions.md`. The 9231 output schema
  is the standard; new subject cutters must match it instead of adding
  subject-specific metadata fields.
- Question-paper JSON sidecars must include a `content` field containing the
  visible question stem/body text for that output question.
- Mark-scheme JSON sidecars must not include `content`, `content_source`, or
  `content_warning`; later structured marking data belongs outside the MS
  sidecar.
- Prefer PDF text/span extraction for `content`; if extracted text is empty,
  clearly mojibake, or otherwise unreliable because of font encoding or damaged
  character maps, run OCR on the rendered question region and store the OCR text
  instead.
- Reports should identify when QP `content` was populated by OCR so later QA
  can audit lower-confidence text.
- Existing sidecar migration/backfill must use recorded `crop_regions` rather
  than rerunning boundary detection.
- QP and MS layouts need separate rules.
- If reliable boundaries cannot be established, fail the paper and report the reason.
- GUI and CLI must call the same shared splitter services.

## Current Subject Support

- `9709`: subject-specific PyMuPDF cutter for QP and MS.
- `9231`: subject-specific PyMuPDF cutter for QP and MS.
- Other subjects currently use the generic fallback until dedicated cutters exist.

## Question Granularity

- Output unit is the leaf question or leaf subquestion.
- Examples: `1`, `2(a)`, `11(c)(ii)`.
- Top-level questions without subparts remain top-level slices.
- Shared stems, diagrams, tables, or givens should be included in each leaf slice when needed for readability.
- QP and MS filenames must use the same normalized question identity.

## Mark Scheme Rules

- Skip generic marking principles, notes, abbreviations, and other front matter.
- Prefer explicit answer-table labels.
- Preserve Answer, Marks, and Guidance columns.
- JSON sidecars must not include `mark_scheme_points`, `image_paths`, or `manifest_path`; downstream structured marking data belongs in storage or later classifier outputs.
- Mark-scheme sidecars must not include `content`, `content_source`, or `content_warning`.

## Concurrency

- `workers=1` preserves sequential splitting.
- Higher values process multiple installed paper sets in parallel.
- The splitter keeps a bounded number of in-flight futures.
- GUI stop prevents new paper sets from being queued while running work finishes.

## Validation

- Compare QP and MS leaf-question counts.
- Confirm every question-paper sidecar has a `content` field.
- Confirm mark-scheme sidecars do not include `content`, `content_source`, or `content_warning`.
- Confirm every CIE A-Level cutter emits the same field set and key types as
  the 9231 metadata schema.
- Spot-check extracted QP `content` against rendered question images, including at
  least one OCR fallback case when available.
- Inspect old and modern layouts.
- Include long answer spaces, cross-page questions, diagrams, matrices, formulas, and dense MS tables.
- Confirm front matter is not cut as a question.
- Confirm representative sidecars can restore images using `crop_regions`.
- Failed papers must appear in reports and must not count as success.
