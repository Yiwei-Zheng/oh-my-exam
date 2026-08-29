from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_extraction import ContentExtraction
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.models import PaperAsset


QP_MANIFEST_KEYS = {
    "question_number",
    "content",
    "source_stem",
    "document_type",
    "source_url",
    "crop_regions",
}
MS_MANIFEST_KEYS = {
    "question_number",
    "source_stem",
    "document_type",
    "source_url",
    "crop_regions",
}
CROP_REGION_KEYS = {
    "order",
    "page_index",
    "rect",
    "render_dpi",
    "join_gap_before_px",
}
OPTIONAL_CROP_REGION_KEYS = {"post_render_crop_px"}


def build_question_manifest(
    asset: PaperAsset,
    question_number: str,
    page_start: int,
    page_end: int,
    cutter: str,
    *,
    content: ContentExtraction | None = None,
    crop_regions: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    regions = [_compact_crop_region(region) for region in (crop_regions or [])]
    source_url = asset.source_url
    if not source_url and crop_regions:
        candidate = crop_regions[0].get("source_pdf")
        source_url = candidate if isinstance(candidate, str) else ""
    manifest: dict[str, object] = {
        "question_number": question_number,
        "source_stem": asset.stem,
        "document_type": asset.document_type,
        "source_url": source_url,
        "crop_regions": regions,
    }
    if asset.document_type == "qp":
        extraction = content or ContentExtraction("", "not_extracted", "content extraction was not run")
        manifest["content"] = extraction.content
    elif asset.document_type != "ms":
        raise ValueError(f"unsupported CIE A-Level document type: {asset.document_type}")
    return manifest


def validate_manifest_schema(manifest: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    document_type = manifest.get("document_type")
    if document_type == "qp":
        allowed_keys = QP_MANIFEST_KEYS
        required_keys = QP_MANIFEST_KEYS
    elif document_type == "ms":
        allowed_keys = MS_MANIFEST_KEYS
        required_keys = MS_MANIFEST_KEYS
    else:
        return [f"document_type must be 'qp' or 'ms', got {document_type!r}"]

    missing = required_keys - manifest.keys()
    extra = manifest.keys() - allowed_keys
    if missing:
        errors.append(f"missing manifest fields: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected manifest fields: {sorted(extra)}")

    errors.extend(_expect_str(manifest, "question_number"))
    errors.extend(_expect_str(manifest, "source_stem"))
    errors.extend(_expect_str(manifest, "source_url"))
    crop_regions = manifest.get("crop_regions")
    if not isinstance(crop_regions, list):
        errors.append("crop_regions must be a list")
    else:
        for index, region in enumerate(crop_regions):
            errors.extend(_validate_crop_region(index, region, str(manifest.get("source_stem")), document_type))
    if document_type == "qp":
        errors.extend(_expect_str(manifest, "content"))
    return errors


def _validate_crop_region(index: int, region: object, source_stem: str, document_type: str) -> list[str]:
    if not isinstance(region, Mapping):
        return [f"crop_regions[{index}] must be an object"]
    errors: list[str] = []
    missing = CROP_REGION_KEYS - region.keys()
    extra = region.keys() - (CROP_REGION_KEYS | OPTIONAL_CROP_REGION_KEYS)
    if missing:
        errors.append(f"crop_regions[{index}] missing fields: {sorted(missing)}")
    if extra:
        errors.append(f"crop_regions[{index}] unexpected fields: {sorted(extra)}")

    for key in ("order", "page_index", "render_dpi", "join_gap_before_px"):
        errors.extend(_expect_int(region, key, prefix=f"crop_regions[{index}]."))

    rect = region.get("rect")
    if not isinstance(rect, Mapping):
        errors.append(f"crop_regions[{index}].rect must be an object")
    else:
        rect_keys = {"x0", "y0", "x1", "y1"}
        missing_rect = rect_keys - rect.keys()
        extra_rect = rect.keys() - rect_keys
        if missing_rect:
            errors.append(f"crop_regions[{index}].rect missing fields: {sorted(missing_rect)}")
        if extra_rect:
            errors.append(f"crop_regions[{index}].rect unexpected fields: {sorted(extra_rect)}")
        for key in rect_keys:
            errors.extend(_expect_number(rect, key, prefix=f"crop_regions[{index}].rect."))

    if "post_render_crop_px" in region and not isinstance(region["post_render_crop_px"], Mapping):
        errors.append(f"crop_regions[{index}].post_render_crop_px must be an object")
    return errors


def _compact_crop_region(region: Mapping[str, object]) -> dict[str, object]:
    compact = {key: region[key] for key in CROP_REGION_KEYS if key in region}
    post_crop = region.get("post_render_crop_px")
    if isinstance(post_crop, Mapping):
        compact["post_render_crop_px"] = {
            key: post_crop[key]
            for key in ("left", "top", "right", "bottom")
            if key in post_crop
        }
    return compact


def _expect_str(mapping: Mapping[str, Any], key: str, *, prefix: str = "") -> list[str]:
    return [] if isinstance(mapping.get(key), str) else [f"{prefix}{key} must be a string"]


def _expect_int(mapping: Mapping[str, Any], key: str, *, prefix: str = "") -> list[str]:
    value = mapping.get(key)
    return [] if isinstance(value, int) and not isinstance(value, bool) else [f"{prefix}{key} must be an integer"]


def _expect_number(mapping: Mapping[str, Any], key: str, *, prefix: str = "") -> list[str]:
    value = mapping.get(key)
    return [] if isinstance(value, (int, float)) and not isinstance(value, bool) else [f"{prefix}{key} must be a number"]
