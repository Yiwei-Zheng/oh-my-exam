# CIE A-Level Crop Regions

## Scope

`crop_regions` metadata written by CIE A-Level splitter JSON sidecars.

## What belongs here

- `crop_regions` purpose.
- Field list.
- Restoration flow.
- Edge cases.

## What does not belong here

- Full processed question sidecar schema.
- Cutter implementation algorithms.
- Downloader raw asset discovery.
- SQLite schema.

## Related docs

- `docs/tools/cie_alevel_splitter/overview.md`
- `docs/tools/cie_alevel_splitter/processed-question-layout.md`
- `docs/tools/cie_alevel_splitter/raw-paper-layout.md`

## Purpose

Each question JSON sidecar must include enough `crop_regions` metadata to recreate the final question image from the original PDF without rerunning boundary detection.

## Schema

`crop_regions` is an ordered list.

Each item describes one source segment and must use the same field set as the
current 9231 output:

- `order`: zero-based join order.
- `page_index`: zero-based source PDF page index.
- `rect`: source crop rectangle with `x0`, `y0`, `x1`, `y1`.
- `render_dpi`: render DPI.
- `join_gap_before_px`: white gap before this segment.
- `post_render_crop_px`: optional pixel crop after rendering.

No other per-region fields are part of the CIE A-Level metadata schema. If a
cutter needs internal replay or QA information, it should keep that in reports
or tool-specific logs rather than adding fields to question sidecars.

`rect` uses the PDF page coordinate space consumed by the runtime renderer.
Source identity and the exact download URL are stored once at sidecar top
level instead of being repeated in every region.

## Restoration Flow

1. Load the JSON sidecar.
2. Sort `crop_regions` by `order`.
3. Resolve the top-level `source_url` to the local raw PDF cache when rebuilding
   locally, or download that exact URL when the local cache is missing.
4. Render `page_index` at `render_dpi` using `rect`.
5. Apply `post_render_crop_px` if present.
6. Join segments vertically.
7. Insert `join_gap_before_px` before non-first segments.

For `pymupdf_page_points`, pass `rect` directly to `page.get_pixmap(..., clip=fitz.Rect(...))`.

## Edge Cases

- Multi-page questions use multiple ordered regions.
- A leaf subquestion may include shared stem regions and its own subpart region.
- Generic fallback regions are lower confidence but must still use this schema.
- Untrusted boundaries should fail the paper instead of writing misleading regions.
