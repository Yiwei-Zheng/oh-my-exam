from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from exam_packer.models import MetadataCourse, MetadataRecord


STEM_RE = re.compile(
    r"^(?P<course_code>[A-Za-z0-9]+)_(?P<session>[mswMSW]\d{2})_(?P<source_type>qp|ms|QP|MS)(?:_(?P<component>[A-Za-z0-9_]+))?$"
)
MODERN_FILE_RE = re.compile(
    r"^(?P<course_code>[A-Za-z0-9]+)_(?P<session>[mswMSW]\d{2})_(?P<source_type>qp|ms|QP|MS)_(?P<component>.+)_(?P<local_question_key>q.+)$"
)
UAT_STEM_RE = re.compile(
    r"^(?P<course_code>[A-Za-z0-9]+)_(?P<year>\d{4})_(?P<component>s\d+)_(?P<source_type>qp|ms|QP|MS)$"
)
UAT_FILE_RE = re.compile(
    r"^(?P<course_code>[A-Za-z0-9]+)_(?P<year>\d{4})_(?P<component>s\d+)_(?P<source_type>qp|ms|QP|MS)_(?P<local_question_key>q.+)$"
)
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
UAT_QP_MANIFEST_KEYS = {
    "question_number",
    "content",
    "source_stem",
    "page_start",
    "page_end",
    "document_type",
    "cutter",
    "content_source",
    "crop_regions",
}
UAT_MS_MANIFEST_KEYS = {
    "question_number",
    "source_stem",
    "page_start",
    "page_end",
    "document_type",
    "cutter",
    "crop_regions",
}
UAT_OPTIONAL_MANIFEST_KEYS = {"content_warning"}
UAT_CROP_REGION_KEYS = CROP_REGION_KEYS | {"source_pdf"}


def load_metadata_records(
    metadata_root: Path,
    *,
    exam_board: str,
    qualification: str,
    course_code: str,
) -> tuple[list[MetadataRecord], list[str]]:
    records: list[MetadataRecord] = []
    warnings: list[str] = []
    prefix = f"{course_code}_".lower()
    paths = [path for path in metadata_root.rglob("*.json") if path.stem.lower().startswith(prefix)]
    workers = min(32, max(4, (os.cpu_count() or 4) * 2))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = executor.map(
            lambda path: _load_one_record(path, metadata_root, exam_board=exam_board, qualification=qualification),
            paths,
        )
        for record, record_warnings in results:
            warnings.extend(record_warnings)
            if record is None:
                continue
            if record.course_code != course_code:
                continue
            records.append(record)
    return records, warnings


def _load_one_record(
    path: Path,
    metadata_root: Path,
    *,
    exam_board: str,
    qualification: str,
) -> tuple[MetadataRecord | None, list[str]]:
    warnings: list[str] = []
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"{path}: failed to read JSON metadata: {exc}"]
    if not isinstance(metadata, dict):
        return None, [f"{path}: skipped because metadata root is not an object"]
    schema_warnings = _validate_metadata_schema(path, metadata)
    if schema_warnings:
        return None, schema_warnings
    record = build_record(path, metadata, metadata_root, exam_board=exam_board, qualification=qualification)
    if record is None:
        return None, [f"{path}: skipped because filename/source_stem does not match splitter metadata naming"]
    warnings.extend(record.warnings)
    return record, warnings


def discover_metadata_courses(metadata_root: Path) -> list[MetadataCourse]:
    counts: dict[tuple[str, str, str], int] = {}
    for path in metadata_root.rglob("*.json"):
        parsed = _parse_identity_from_path(path)
        if parsed is None:
            continue
        exam_board, qualification = _infer_board_qualification(path, parsed["course_code"])
        key = (exam_board, qualification, parsed["course_code"])
        counts[key] = counts.get(key, 0) + 1
    return [
        MetadataCourse(qualification=qualification, exam_board=exam_board, course_code=course_code, metadata_count=count)
        for (exam_board, qualification, course_code), count in sorted(counts.items())
    ]


def build_record(
    path: Path,
    metadata: dict[str, Any],
    metadata_root: Path,
    *,
    exam_board: str,
    qualification: str,
) -> MetadataRecord | None:
    parsed = _parse_identity(path, metadata)
    if parsed is None:
        return None

    crop_regions = metadata.get("crop_regions")
    warnings: list[str] = []
    if not isinstance(crop_regions, list):
        return None
    warnings.extend(_validate_crop_region_document_identity(path, crop_regions))

    source_type = parsed["source_type"].upper()
    source_url = _source_url(metadata)
    component = parsed["component"]
    paper_key = _paper_key(parsed["source_stem"], parsed["source_type"])
    local_question_key = parsed["local_question_key"]
    question_key = f"{paper_key}_{local_question_key}"
    paper_code = component[0] if component else ""
    variant = component[1:] if len(component) > 1 else ""
    session = parsed.get("session", parsed.get("year", "")).lower()
    year = int(parsed["year"]) if "year" in parsed else 2000 + int(session[1:3])
    image_path = _find_image_for_sidecar(path)

    return MetadataRecord(
        metadata_path=path,
        metadata=metadata,
        exam_board=_snake_case(exam_board),
        qualification=_snake_case(qualification),
        course_code=parsed["course_code"],
        session=session,
        year=year,
        paper_code=paper_code,
        variant=variant,
        component=component,
        paper_key=paper_key,
        source_type=source_type,
        source_stem=parsed["source_stem"],
        source_url=source_url,
        question_key=question_key,
        local_question_key=local_question_key,
        image_path=image_path,
        crop_regions=crop_regions,
        warnings=warnings,
    )


def metadata_extra_fields(metadata: dict[str, Any], stable_fields: Iterable[str]) -> dict[str, Any]:
    stable = set(stable_fields)
    return {key: value for key, value in metadata.items() if key not in stable}


def crop_region_extra_fields(region: dict[str, Any]) -> dict[str, Any]:
    stable = {
        "order",
        "page_index",
        "rect",
        "render_dpi",
        "join_gap_before_px",
        "post_render_crop_px",
    }
    return {key: value for key, value in region.items() if key not in stable}


def _parse_identity(path: Path, metadata: dict[str, Any]) -> dict[str, str] | None:
    source_stem_value = metadata.get("source_stem")
    if not isinstance(source_stem_value, str):
        return None
    source_stem = source_stem_value
    stem_match = STEM_RE.match(source_stem)
    file_match = MODERN_FILE_RE.match(path.stem)
    schema = "cie"
    if stem_match is None or file_match is None:
        stem_match = UAT_STEM_RE.match(source_stem)
        file_match = UAT_FILE_RE.match(path.stem)
        schema = "uat"
    if stem_match is None:
        return None
    if file_match is None:
        return None
    document_type = metadata.get("document_type")
    if document_type not in {"qp", "ms"}:
        return None
    parsed = file_match.groupdict()
    component = stem_match.group("component")
    if not component:
        return None
    period_matches = (
        parsed["session"].lower() == stem_match.group("session").lower()
        if schema == "cie"
        else parsed["year"] == stem_match.group("year")
    )
    if (
        parsed["course_code"] != stem_match.group("course_code")
        or not period_matches
        or parsed["source_type"].lower() != stem_match.group("source_type").lower()
        or parsed["source_type"].lower() != document_type
        or parsed["component"] != component
    ):
        return None
    parsed["source_stem"] = source_stem
    if schema == "cie":
        parsed["session"] = stem_match.group("session").lower()
    else:
        parsed["year"] = stem_match.group("year")
    parsed["source_type"] = document_type.upper()
    parsed["component"] = component
    parsed["course_code"] = stem_match.group("course_code")
    parsed["schema"] = schema
    return parsed


def _parse_identity_from_path(path: Path) -> dict[str, str] | None:
    file_match = MODERN_FILE_RE.match(path.stem)
    schema = "cie"
    if file_match is None:
        file_match = UAT_FILE_RE.match(path.stem)
        schema = "uat"
    if file_match is None:
        return None
    parsed = file_match.groupdict()
    if schema == "cie":
        parsed["session"] = parsed["session"].lower()
    parsed["source_type"] = parsed["source_type"].upper()
    parsed["component"] = parsed.get("component") or _component_from_path(path)
    parsed["schema"] = schema
    if not parsed["component"]:
        return None
    return parsed


def _component_from_path(path: Path) -> str:
    if path.parent.name.lower() in {"qp", "ms"}:
        return path.parent.parent.name
    return ""


def _infer_board_qualification(path: Path, course_code: str) -> tuple[str, str]:
    parts = list(path.parts)
    if course_code in parts:
        index = parts.index(course_code)
        if index >= 2:
            return _snake_case(parts[index - 2]), _snake_case(parts[index - 1])
    return "cie", "a_level"


def _find_image_for_sidecar(path: Path) -> Path | None:
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        candidate = path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def _validate_crop_region_document_identity(path: Path, regions: list[Any]) -> list[str]:
    return [f"{path}: crop_regions[{index}] is not an object" for index, region in enumerate(regions) if not isinstance(region, dict)]


def _validate_metadata_schema(path: Path, metadata: dict[str, Any]) -> list[str]:
    parsed = _parse_identity(path, metadata)
    if parsed is None:
        return [f"{path}: skipped because metadata does not match unified CIE A-Level splitter schema"]

    document_type = metadata["document_type"]
    is_uat = parsed["schema"] == "uat"
    if is_uat and document_type == "qp":
        required = UAT_QP_MANIFEST_KEYS
        allowed = UAT_QP_MANIFEST_KEYS | UAT_OPTIONAL_MANIFEST_KEYS
    elif is_uat:
        required = UAT_MS_MANIFEST_KEYS
        allowed = UAT_MS_MANIFEST_KEYS
    elif document_type == "qp":
        required = QP_MANIFEST_KEYS
        allowed = QP_MANIFEST_KEYS
    else:
        required = MS_MANIFEST_KEYS
        allowed = MS_MANIFEST_KEYS
    errors: list[str] = []
    missing = required - metadata.keys()
    extra = metadata.keys() - allowed
    if missing:
        errors.append(f"{path}: missing metadata fields {sorted(missing)}")
    if extra:
        errors.append(f"{path}: unexpected metadata fields {sorted(extra)}")

    errors.extend(_expect_str(path, metadata, "question_number"))
    errors.extend(_expect_str(path, metadata, "source_stem"))
    if is_uat:
        errors.extend(_expect_int(path, metadata, "page_start"))
        errors.extend(_expect_int(path, metadata, "page_end"))
        errors.extend(_expect_str(path, metadata, "cutter"))
    else:
        errors.extend(_expect_str(path, metadata, "source_url"))
    if document_type == "qp":
        errors.extend(_expect_str(path, metadata, "content"))

    crop_regions = metadata.get("crop_regions")
    if not isinstance(crop_regions, list):
        errors.append(f"{path}: crop_regions must be a list")
    else:
        for index, region in enumerate(crop_regions):
            errors.extend(
                _validate_crop_region_schema(
                    path,
                    index,
                    region,
                    parsed["source_stem"],
                    document_type,
                    is_uat=is_uat,
                )
            )
    return errors


def _validate_crop_region_schema(
    path: Path,
    index: int,
    region: Any,
    source_stem: str,
    document_type: str,
    *,
    is_uat: bool,
) -> list[str]:
    prefix = f"{path}: crop_regions[{index}]"
    if not isinstance(region, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    required_keys = UAT_CROP_REGION_KEYS if is_uat else CROP_REGION_KEYS
    missing = required_keys - region.keys()
    extra = set() if is_uat else region.keys() - (CROP_REGION_KEYS | OPTIONAL_CROP_REGION_KEYS)
    if missing:
        errors.append(f"{prefix} missing fields {sorted(missing)}")
    if extra:
        errors.append(f"{prefix} unexpected fields {sorted(extra)}")
    for key in ("order", "page_index", "render_dpi", "join_gap_before_px"):
        errors.extend(_expect_int(path, region, key, prefix=f"crop_regions[{index}]."))
    rect = region.get("rect")
    if not isinstance(rect, dict):
        errors.append(f"{prefix}.rect must be an object")
    else:
        rect_keys = {"x0", "y0", "x1", "y1"}
        missing_rect = rect_keys - rect.keys()
        extra_rect = rect.keys() - rect_keys
        if missing_rect:
            errors.append(f"{prefix}.rect missing fields {sorted(missing_rect)}")
        if extra_rect:
            errors.append(f"{prefix}.rect unexpected fields {sorted(extra_rect)}")
        for key in rect_keys:
            errors.extend(_expect_number(path, rect, key, prefix=f"crop_regions[{index}].rect."))
    if "post_render_crop_px" in region and not isinstance(region["post_render_crop_px"], dict):
        errors.append(f"{prefix}.post_render_crop_px must be an object")
    if is_uat:
        errors.extend(_expect_str(path, region, "source_pdf", prefix=f"crop_regions[{index}]."))
    return errors


def _source_url(metadata: dict[str, Any]) -> str:
    value = metadata.get("source_url")
    if isinstance(value, str):
        return value
    regions = metadata.get("crop_regions")
    if isinstance(regions, list):
        for region in regions:
            if isinstance(region, dict) and isinstance(region.get("source_pdf"), str):
                return region["source_pdf"]
    return ""


def _paper_key(source_stem: str, source_type: str) -> str:
    marker = f"_{source_type.lower()}_"
    if marker in source_stem:
        return source_stem.replace(marker, "_", 1)
    suffix = f"_{source_type.lower()}"
    return source_stem[: -len(suffix)] if source_stem.endswith(suffix) else source_stem


def _expect_str(path: Path, mapping: dict[str, Any], key: str, *, prefix: str = "") -> list[str]:
    return [] if isinstance(mapping.get(key), str) else [f"{path}: {prefix}{key} must be a string"]


def _expect_int(path: Path, mapping: dict[str, Any], key: str, *, prefix: str = "") -> list[str]:
    value = mapping.get(key)
    return [] if isinstance(value, int) and not isinstance(value, bool) else [f"{path}: {prefix}{key} must be an integer"]


def _expect_number(path: Path, mapping: dict[str, Any], key: str, *, prefix: str = "") -> list[str]:
    value = mapping.get(key)
    return [] if isinstance(value, (int, float)) and not isinstance(value, bool) else [f"{path}: {prefix}{key} must be a number"]


def _snake_case(value: str) -> str:
    clean = re.sub(r"[^0-9A-Za-z]+", "_", value.strip()).strip("_").lower()
    return clean or "unknown"
