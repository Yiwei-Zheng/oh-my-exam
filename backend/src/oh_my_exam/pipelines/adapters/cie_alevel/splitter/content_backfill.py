from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_extraction import extract_content_from_fitz_clips
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.paths import find_project_root


def backfill_processed_question_content(
    processed_root: Path,
    *,
    limit: int | None = None,
    overwrite: bool = False,
) -> dict[str, int]:
    fitz = _load_fitz()
    counts = {"updated": 0, "skipped": 0, "failed": 0}
    project_root = find_project_root(processed_root)
    sidecars = sorted(processed_root.rglob("*.json"))
    if limit is not None:
        sidecars = sidecars[:limit]
    for sidecar_path in sidecars:
        try:
            manifest = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if manifest.get("document_type") == "ms":
                _remove_content_fields(manifest)
                sidecar_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                counts["skipped"] += 1
                continue
            if manifest.get("content") and not overwrite:
                counts["skipped"] += 1
                continue
            crop_regions = manifest.get("crop_regions")
            if not isinstance(crop_regions, list) or not crop_regions:
                counts["failed"] += 1
                continue
            source_pdf = _source_pdf_path(manifest, crop_regions[0], project_root)
            clips = _clips_from_crop_regions(fitz, source_pdf, crop_regions)
            image = _load_sidecar_image(sidecar_path)
            with fitz.open(source_pdf) as document:
                extraction = extract_content_from_fitz_clips(document, clips, image)
            manifest["content"] = extraction.content
            sidecar_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            counts["updated"] += 1
        except Exception:
            counts["failed"] += 1
    return counts


def _remove_content_fields(manifest: dict[str, object]) -> None:
    manifest.pop("content", None)
    manifest.pop("content_source", None)
    manifest.pop("content_warning", None)


def _load_fitz():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Content backfill requires PyMuPDF. Install with: python -m pip install PyMuPDF") from exc
    return fitz


def _source_pdf_path(manifest: dict[str, object], crop_region: dict[str, object], project_root: Path) -> Path:
    source_pdf = manifest.get("source_url") or crop_region.get("source_pdf")
    if not isinstance(source_pdf, str) or not source_pdf:
        raise ValueError("crop region does not record source_pdf")
    if source_pdf.startswith(("http://", "https://")):
        return _local_source_pdf_path_from_url(source_pdf, project_root)
    path = Path(source_pdf)
    return path if path.is_absolute() else project_root / path


def _local_source_pdf_path_from_url(source_pdf: str, project_root: Path) -> Path:
    stem = Path(urlparse(source_pdf).path).stem
    parts = stem.split("_")
    if len(parts) < 3:
        raise ValueError(f"cannot infer local raw PDF path from URL: {source_pdf}")
    subject_code = parts[0]
    session = parts[1]
    year = 2000 + int(session[1:3])
    current = project_root / "backend" / "data" / "raw_papers" / "cie" / "a_level" / subject_code / str(year) / session / f"{stem}.pdf"
    if current.exists():
        return current
    legacy = project_root / "backend" / "data" / "raw_papers" / "cie" / "a_level" / subject_code / session / f"{stem}.pdf"
    return legacy if legacy.exists() else current


def _clips_from_crop_regions(fitz, source_pdf: Path, crop_regions: list[object]) -> list[tuple[int, object]]:
    clips: list[tuple[int, object]] = []
    with fitz.open(source_pdf) as document:
        for region in crop_regions:
            if not isinstance(region, dict):
                continue
            page_index = int(region["page_index"])
            rect_payload = region["rect"]
            if not isinstance(rect_payload, dict):
                continue
            rect = _rect_from_payload(fitz, document[page_index], region, rect_payload)
            clips.append((page_index, rect))
    if not clips:
        raise ValueError("no supported crop regions found")
    return clips


def _rect_from_payload(fitz, page, region: dict[str, object], rect_payload: dict[str, object]):
    x0 = float(rect_payload["x0"])
    y0 = float(rect_payload["y0"])
    x1 = float(rect_payload["x1"])
    y1 = float(rect_payload["y1"])
    coordinate_space = region.get("coordinate_space")
    if coordinate_space == "pymupdf_page_points":
        return fitz.Rect(x0, y0, x1, y1)
    if coordinate_space == "pypdf_mediabox_points_bottom_left":
        return fitz.Rect(x0, page.rect.height - y1, x1, page.rect.height - y0)
    raise ValueError(f"unsupported crop region coordinate space: {coordinate_space}")


def _load_sidecar_image(sidecar_path: Path):
    image_path = _sidecar_image_path(sidecar_path)
    if image_path is None:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        return Image.open(image_path).convert("L")
    except OSError:
        return None


def _sidecar_image_path(sidecar_path: Path) -> Path | None:
    for suffix in (".jpg", ".jpeg", ".png"):
        candidate = sidecar_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None
