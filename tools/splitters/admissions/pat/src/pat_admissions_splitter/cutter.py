from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image

from pat_admissions_splitter.models import PaperAsset


@dataclass(frozen=True)
class SplitOptions:
    dpi: int = 180
    quality: int = 90
    horizontal_margin: float = 36.0
    top_padding: float = 4.0
    bottom_padding: float = 8.0
    join_gap_px: int = 20
    ocr_dpi: int = 150
    prefer_gpu: bool = True


@dataclass(frozen=True)
class Anchor:
    number: int
    page_index: int
    rect: fitz.Rect
    source: str


@dataclass(frozen=True)
class OCRLine:
    text: str
    rect: fitz.Rect


_OCR_PAGE_CACHE: dict[tuple[str, int, int, bool], tuple[OCRLine, ...]] = {}
_DLL_DIRECTORY_HANDLES: list[object] = []


def split_asset(asset: PaperAsset, processed_root: Path, options: SplitOptions | None = None) -> list[dict[str, object]]:
    options = options or SplitOptions()
    output_dir = processed_root / asset.output_relative_dir
    temp_dir = output_dir.parent / f".{output_dir.name}-{asset.stem}-tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    source_sha256 = asset.source_sha256 or _sha256(asset.pdf_path)
    try:
        with fitz.open(asset.pdf_path) as document:
            try:
                anchors = _find_anchors(document, asset, options)
                plans = _crop_plans(document, anchors, options)
                cutter_name = "pat_admissions_geometry_v1"
            except RuntimeError:
                if asset.document_type != "ms":
                    raise
                plans = _fallback_solution_plans(document, asset, options)
                cutter_name = "pat_admissions_solution_page_fallback_v1"
            results: list[dict[str, object]] = []
            for ordinal, clips in plans:
                rendered = _render_clips(document, clips, options)
                key = f"q{ordinal:02d}"
                image_name = f"{asset.stem}_{key}.jpg"
                manifest_name = f"{asset.stem}_{key}.json"
                rendered.save(temp_dir / image_name, format="JPEG", quality=options.quality, optimize=True)
                manifest = _manifest(asset, ordinal, document, clips, source_sha256, options, rendered, cutter_name)
                (temp_dir / manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
                results.append({"question_number": str(ordinal), "image_path": output_dir / image_name, "manifest_path": output_dir / manifest_name})
        output_dir.mkdir(parents=True, exist_ok=True)
        for stale in output_dir.glob(f"{asset.stem}_q*.*"):
            stale.unlink()
        for completed in temp_dir.iterdir():
            completed.replace(output_dir / completed.name)
        temp_dir.rmdir()
        return results
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _find_anchors(document: fitz.Document, asset: PaperAsset, options: SplitOptions) -> list[Anchor]:
    if asset.year == 2024 and len(document) == 41:
        return [Anchor(number, number, fitz.Rect(0, 0, document[number].rect.width, 1), "one_question_per_page") for number in range(1, 41)]

    candidates = _pdf_text_candidates(document)
    anchors = _select_anchors(candidates, asset.year)
    expected = _declared_question_count(document)
    if len(anchors) < 2 or (expected is not None and len(anchors) != expected):
        ocr_candidates = _ocr_candidates(document, options)
        ocr_anchors = _select_anchors(ocr_candidates, asset.year)
        combined_anchors = _select_anchors(candidates + ocr_candidates, asset.year)
        anchors = max((anchors, ocr_anchors, combined_anchors), key=len)
    if len(anchors) < 2:
        raise RuntimeError("trusted PAT question sequence was not found")
    if expected is not None and len(anchors) != expected:
        raise RuntimeError(f"PAT paper declares {expected} questions but {len(anchors)} were found")
    if asset.document_type == "ms":
        reference_count = len(_reference_anchors(asset, options))
        if len(anchors) != reference_count:
            raise RuntimeError(f"PAT solution has {len(anchors)} questions but paired QP has {reference_count}")
    return anchors


def _pdf_text_candidates(document: fitz.Document) -> list[Anchor]:
    candidates: list[Anchor] = []
    heading_re = re.compile(r"^\s*(\d{1,2})\s*[.)]\s+", re.IGNORECASE)
    for page_index, page in enumerate(document):
        for block in page.get_text("blocks", sort=True):
            clean = " ".join(str(block[4]).split())
            match = heading_re.match(clean)
            if match and block[0] <= min(170.0, page.rect.width * 0.3):
                candidates.append(Anchor(int(match.group(1)), page_index, fitz.Rect(block[:4]), "pdf_block"))
        for word in page.get_text("words", sort=True):
            match = re.fullmatch(r"(\d{1,2})[.)]", word[4])
            if match and word[0] <= min(170.0, page.rect.width * 0.3):
                candidates.append(Anchor(int(match.group(1)), page_index, fitz.Rect(word[:4]), "pdf_word"))
    return candidates


def _ocr_candidates(document: fitz.Document, options: SplitOptions) -> list[Anchor]:
    candidates: list[Anchor] = []
    heading_re = re.compile(r"^\s*(?:Q(?:uestion)?\s*)?(\d{1,2})\s*[.)]\s*", re.IGNORECASE)
    for page_index, page in enumerate(document):
        for line in _ocr_page_lines(document, page_index, options):
            match = heading_re.match(line.text)
            if match and line.rect.x0 <= min(170.0, page.rect.width * 0.3):
                candidates.append(Anchor(int(match.group(1)), page_index, line.rect, "ocr"))
    return candidates


def _select_anchors(candidates: list[Anchor], year: int) -> list[Anchor]:
    if not candidates:
        return []
    ordered = sorted(candidates, key=lambda item: (item.page_index, item.rect.y0, item.rect.x0, item.source))
    sequences = [_sequence_from_start(ordered, index) for index, item in enumerate(ordered) if item.number == 1]
    sequences = [sequence for sequence in sequences if len(sequence) >= 2]
    if not sequences:
        return []
    if year > 2007:
        return max(sequences, key=lambda sequence: (len(sequence), -sequence[0].page_index, -sequence[0].rect.y0))
    selected: list[list[Anchor]] = []
    for sequence in sorted(sequences, key=lambda item: (-len(item), item[0].page_index, item[0].rect.y0)):
        occupied = {(anchor.page_index, round(anchor.rect.y0, 1)) for group in selected for anchor in group}
        identity = {(anchor.page_index, round(anchor.rect.y0, 1)) for anchor in sequence}
        if not occupied.intersection(identity):
            selected.append(sequence)
        if len(selected) == 2:
            break
    if len(selected) != 2:
        return []
    selected.sort(key=lambda sequence: (sequence[0].page_index, sequence[0].rect.y0))
    return [anchor for sequence in selected for anchor in sequence]


def _sequence_from_start(ordered: list[Anchor], start_index: int) -> list[Anchor]:
    first = ordered[start_index]
    sequence = [first]
    expected = 2
    reference_x = first.rect.x0
    for item in ordered[start_index + 1 :]:
        if item.number == expected and abs(item.rect.x0 - reference_x) <= 38.0:
            sequence.append(item)
            expected += 1
    return sequence


def _declared_question_count(document: fitz.Document) -> int | None:
    front_text = " ".join(document[index].get_text("text") for index in range(min(3, len(document))))
    match = re.search(r"(?:total\s+)?(\d{1,2})\s+questions", front_text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _crop_plans(document: fitz.Document, anchors: list[Anchor], options: SplitOptions) -> list[tuple[int, list[tuple[int, fitz.Rect]]]]:
    plans: list[tuple[int, list[tuple[int, fitz.Rect]]]] = []
    for index, anchor in enumerate(anchors):
        following = anchors[index + 1] if index + 1 < len(anchors) else None
        last_page = following.page_index if following else len(document) - 1
        clips: list[tuple[int, fitz.Rect]] = []
        for page_index in range(anchor.page_index, last_page + 1):
            page = document[page_index]
            if page_index > anchor.page_index and _is_blank_page(document, page_index, options):
                continue
            top = anchor.rect.y0 - options.top_padding if page_index == anchor.page_index else 28.0
            if following and page_index == following.page_index:
                if page_index == anchor.page_index:
                    bottom = following.rect.y0 - options.top_padding
                else:
                    break
            else:
                bottom = _content_bottom(page, top, options.bottom_padding)
            margin = 20.0 if anchor.source == "one_question_per_page" else options.horizontal_margin
            rect = fitz.Rect(margin, max(0.0, top), page.rect.width - margin, min(page.rect.height, bottom))
            if rect.height > 8:
                clips.append((page_index, rect))
        if not clips:
            raise RuntimeError(f"PAT question {index + 1} produced no trusted crop regions")
        plans.append((index + 1, clips))
    return plans


def _fallback_solution_plans(
    document: fitz.Document,
    asset: PaperAsset,
    options: SplitOptions,
) -> list[tuple[int, list[tuple[int, fitz.Rect]]]]:
    reference = _reference_anchors(asset, options)
    expected_groups = _split_numbering_groups(reference)
    candidates = sorted(
        _pdf_text_candidates(document) + _ocr_candidates(document, options),
        key=lambda item: (item.page_index, item.rect.y0, item.rect.x0),
    )
    candidate_groups = _candidate_numbering_groups(candidates, expected_groups, document, options)
    if len(candidate_groups) != len(expected_groups):
        raise RuntimeError("PAT solution fallback could not locate each numbered section")

    plans: list[tuple[int, list[tuple[int, fitz.Rect]]]] = []
    ordinal = 1
    for expected, (group_candidates, section_start, section_end) in zip(expected_groups, candidate_groups):
        first_by_number: dict[int, Anchor] = {}
        for candidate in group_candidates:
            first_by_number.setdefault(candidate.number, candidate)
        detected = sorted(first_by_number.items())
        for printed_number in expected:
            previous_pages = [anchor.page_index for number, anchor in detected if number <= printed_number]
            following_pages = [anchor.page_index for number, anchor in detected if number >= printed_number]
            start_page = max(previous_pages, default=section_start)
            end_page = min(following_pages, default=section_end)
            if end_page < start_page:
                end_page = start_page
            clips = []
            for page_index in range(start_page, end_page + 1):
                if page_index > start_page and _is_blank_page(document, page_index, options):
                    continue
                page = document[page_index]
                clips.append((page_index, fitz.Rect(20.0, 16.0, page.rect.width - 20.0, page.rect.height - 16.0)))
            if not clips:
                raise RuntimeError(f"PAT solution fallback produced no crop for question {ordinal}")
            plans.append((ordinal, clips))
            ordinal += 1
    return plans


def _reference_anchors(asset: PaperAsset, options: SplitOptions) -> list[Anchor]:
    qp_path = asset.pdf_path.with_name(asset.pdf_path.name.replace("_ms.pdf", "_qp.pdf"))
    if not qp_path.exists():
        raise RuntimeError("PAT solution processing requires the paired question paper")
    qp_asset = PaperAsset(
        year=asset.year,
        component=asset.component,
        document_type="qp",
        pdf_path=qp_path,
        source_url="",
        source_sha256="",
    )
    with fitz.open(qp_path) as qp_document:
        reference = _select_anchors(_pdf_text_candidates(qp_document), asset.year)
        return reference if len(reference) >= 2 else _find_anchors(qp_document, qp_asset, options)


def _split_numbering_groups(anchors: list[Anchor]) -> list[list[int]]:
    groups: list[list[int]] = []
    for anchor in anchors:
        if anchor.number == 1:
            groups.append([])
        if not groups:
            groups.append([])
        groups[-1].append(anchor.number)
    return groups


def _candidate_numbering_groups(
    candidates: list[Anchor],
    expected_groups: list[list[int]],
    document: fitz.Document,
    options: SplitOptions,
) -> list[tuple[list[Anchor], int, int]]:
    expected_group_count = len(expected_groups)
    starts = [index for index, candidate in enumerate(candidates) if candidate.number == 1]
    if len(starts) >= expected_group_count:
        page_starts = [candidates[index].page_index for index in starts[:expected_group_count]]
    else:
        page_starts = [0]
        for page_index in range(1, len(document)):
            page_text = " ".join(line.text.upper() for line in _ocr_page_lines(document, page_index, options))
            if "MATHEMAT" in page_text:
                page_starts.append(page_index)
                break
        if len(page_starts) < expected_group_count:
            total = sum(len(group) for group in expected_groups)
            page_starts = [0]
            completed = 0
            for group in expected_groups[:-1]:
                completed += len(group)
                page_starts.append(min(len(document) - 1, round(len(document) * completed / total)))
    page_starts = sorted(set(page_starts[:expected_group_count]))
    if len(page_starts) != expected_group_count:
        return []
    groups: list[tuple[list[Anchor], int, int]] = []
    for group_index, start_page in enumerate(page_starts):
        next_page = page_starts[group_index + 1] if group_index + 1 < len(page_starts) else len(document)
        group = [candidate for candidate in candidates if start_page <= candidate.page_index < next_page]
        end_page = next_page - 1
        groups.append((group, start_page, max(start_page, end_page)))
    return groups


def _is_blank_page(document: fitz.Document, page_index: int, options: SplitOptions) -> bool:
    page = document[page_index]
    text = " ".join(page.get_text("text").upper().split())
    if "BLANK PAGE" in text or "INTENTIONALLY LEFT BLANK" in text or "INTENTIONALLY BLANK" in text:
        return True
    cache_key = (str(document.name), page_index, options.ocr_dpi, options.prefer_gpu)
    cached = _OCR_PAGE_CACHE.get(cache_key)
    if cached is not None:
        ocr_text = " ".join(line.text.upper() for line in cached)
        return "BLANK PAGE" in ocr_text or "INTENTIONALLY LEFT BLANK" in ocr_text or "INTENTIONALLY BLANK" in ocr_text
    return not text and not page.get_images(full=True)


def _content_bottom(page: fitz.Page, top: float, padding: float) -> float:
    bottoms = [word[3] for word in page.get_text("words") if top <= word[1] < page.rect.height - 38]
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect and rect.y1 >= top and rect.y0 < page.rect.height - 30:
            bottoms.append(rect.y1)
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            if rect.y1 >= top:
                bottoms.append(min(rect.y1, page.rect.height - 24))
    return min(page.rect.height - 20, max(bottoms, default=page.rect.height - 32) + padding)


def _render_clips(document: fitz.Document, clips: Iterable[tuple[int, fitz.Rect]], options: SplitOptions) -> Image.Image:
    images: list[Image.Image] = []
    matrix = fitz.Matrix(options.dpi / 72.0, options.dpi / 72.0)
    for page_index, rect in clips:
        pixmap = document[page_index].get_pixmap(matrix=matrix, clip=rect, colorspace=fitz.csGRAY, alpha=False)
        images.append(Image.frombytes("L", (pixmap.width, pixmap.height), pixmap.samples))
    width = max(image.width for image in images)
    height = sum(image.height for image in images) + options.join_gap_px * (len(images) - 1)
    joined = Image.new("L", (width, height), 255)
    y = 0
    for image in images:
        joined.paste(image, (0, y))
        y += image.height + options.join_gap_px
    return joined


def _manifest(
    asset: PaperAsset,
    ordinal: int,
    document: fitz.Document,
    clips: list[tuple[int, fitz.Rect]],
    source_sha256: str,
    options: SplitOptions,
    rendered: Image.Image,
    cutter_name: str,
) -> dict[str, object]:
    regions = []
    for order, (page_index, rect) in enumerate(clips):
        page = document[page_index]
        regions.append({
            "order": order,
            "source_pdf": asset.source_url,
            "source_pdf_sha256": source_sha256,
            "source_stem": asset.stem,
            "document_type": asset.document_type,
            "page_index": page_index,
            "page_number": page_index + 1,
            "page_width": page.rect.width,
            "page_height": page.rect.height,
            "page_rotation": page.rotation,
            "coordinate_space": "pymupdf_page_points",
            "unit": "pt",
            "rect": {"x0": rect.x0, "y0": rect.y0, "x1": rect.x1, "y1": rect.y1},
            "render_dpi": options.dpi,
            "join_gap_before_px": 0 if order == 0 else options.join_gap_px,
        })
    manifest: dict[str, object] = {
        "question_number": str(ordinal),
        "source_stem": asset.stem,
        "page_start": clips[0][0] + 1,
        "page_end": clips[-1][0] + 1,
        "document_type": asset.document_type,
        "cutter": cutter_name,
        "crop_regions": regions,
    }
    if asset.document_type == "qp":
        content = _normalize_text("\n".join(document[page_index].get_text("text", clip=rect, sort=True) for page_index, rect in clips))
        content_source = "pdf_text"
        warning = ""
        if _text_is_unreliable(content):
            content = _ocr_clip_text(document, clips, options)
            if not content:
                content, warning = _ocr_text(rendered, options)
            content_source = "ocr" if content else "ocr_unavailable"
        manifest["content"] = content
        manifest["content_source"] = content_source
        if warning:
            manifest["content_warning"] = warning
    return manifest


def _ocr_page_lines(document: fitz.Document, page_index: int, options: SplitOptions) -> tuple[OCRLine, ...]:
    key = (str(document.name), page_index, options.ocr_dpi, options.prefer_gpu)
    cached = _OCR_PAGE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("scanned PAT paper requires RapidOCR and ONNX Runtime") from exc
    page = document[page_index]
    scale = options.ocr_dpi / 72.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    try:
        result = _rapidocr(options.prefer_gpu)(image, use_det=True, use_cls=True, use_rec=True)
    except Exception as exc:
        raise RuntimeError(f"RapidOCR failed: {exc}") from exc
    lines: list[OCRLine] = []
    if result.txts and result.boxes is not None:
        for text, box in zip(result.txts, result.boxes):
            clean = str(text).strip()
            if clean:
                lines.append(OCRLine(clean, fitz.Rect(
                    float(min(point[0] for point in box)) / scale,
                    float(min(point[1] for point in box)) / scale,
                    float(max(point[0] for point in box)) / scale,
                    float(max(point[1] for point in box)) / scale,
                )))
    cached = tuple(lines)
    _OCR_PAGE_CACHE[key] = cached
    return cached


def _ocr_clip_text(document: fitz.Document, clips: list[tuple[int, fitz.Rect]], options: SplitOptions) -> str:
    selected: list[str] = []
    for page_index, clip in clips:
        for line in _ocr_page_lines(document, page_index, options):
            center = fitz.Point((line.rect.x0 + line.rect.x1) / 2, (line.rect.y0 + line.rect.y1) / 2)
            if clip.contains(center):
                selected.append(line.text)
    return _normalize_text("\n".join(selected))


def _ocr_text(image: Image.Image, options: SplitOptions) -> tuple[str, str]:
    try:
        import numpy as np

        result = _rapidocr(options.prefer_gpu)(np.asarray(image.convert("RGB")), use_det=True, use_cls=True, use_rec=True)
        return _normalize_text("\n".join(result.txts or ())), ""
    except Exception as exc:
        return "", f"OCR fallback failed: {exc}"


@lru_cache(maxsize=2)
def _rapidocr(prefer_gpu: bool):
    try:
        import onnxruntime as ort
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError("RapidOCR and ONNX Runtime are required for scanned PAT papers") from exc
    use_cuda = prefer_gpu and "CUDAExecutionProvider" in ort.get_available_providers()
    if use_cuda:
        try:
            nvidia_root = Path(ort.__file__).resolve().parent.parent / "nvidia"
            bin_dirs = sorted(nvidia_root.glob("*/bin"))
            if os.name == "nt":
                for bin_dir in bin_dirs:
                    _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(bin_dir)))
                os.environ["PATH"] = os.pathsep.join(str(path) for path in bin_dirs) + os.pathsep + os.environ.get("PATH", "")
            if hasattr(ort, "preload_dlls"):
                ort.preload_dlls(directory="")
        except Exception:
            use_cuda = False
    return RapidOCR(params={"EngineConfig.onnxruntime.use_cuda": use_cuda})


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _text_is_unreliable(text: str) -> bool:
    meaningful = [character for character in text if not character.isspace()]
    if len(meaningful) < 80 or "Firefox\nabout:blank" in text or "\ufffd" in text:
        return True
    suspicious = sum(1 for character in meaningful if character in {"□", "�"} or 0xE000 <= ord(character) <= 0xF8FF)
    return suspicious / len(meaningful) > 0.12


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
