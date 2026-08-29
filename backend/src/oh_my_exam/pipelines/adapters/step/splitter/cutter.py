from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image

from oh_my_exam.pipelines.adapters.step.splitter.models import PaperAsset


@dataclass(frozen=True)
class SplitOptions:
    dpi: int = 180
    quality: int = 90
    horizontal_margin: float = 36.0
    top_padding: float = 4.0
    bottom_padding: float = 8.0
    join_gap_px: int = 20
    ocr_dpi: int = 220


@dataclass(frozen=True)
class Anchor:
    number: int
    page_index: int
    rect: fitz.Rect
    source: str


@dataclass(frozen=True)
class AnchorSelection:
    anchors: tuple[Anchor, ...]
    stop: Anchor | None = None


@dataclass(frozen=True)
class OCRLine:
    text: str
    rect: fitz.Rect


_OCR_PAGE_CACHE: dict[tuple[object, int, int], tuple[OCRLine, ...]] = {}
_OCR_COLUMN_CACHE: dict[tuple[object, int, float, bool], tuple[Anchor, ...]] = {}
_DLL_DIRECTORY_HANDLES: list[object] = []


def split_asset(asset: PaperAsset, processed_root: Path, options: SplitOptions | None = None) -> list[dict[str, object]]:
    options = options or SplitOptions()
    output_dir = processed_root / asset.output_relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    source_sha256 = asset.source_sha256 or _sha256(asset.pdf_path)
    with fitz.open(asset.pdf_path) as document:
        bundle_index = asset.contains_papers.index(asset.paper) if asset.paper in asset.contains_papers else None
        bundle_count = len(asset.contains_papers)
        selection = _find_anchors(document, asset.document_type, options, bundle_index, bundle_count)
        plans = _crop_plans(document, list(selection.anchors), options, selection.stop)
        results: list[dict[str, object]] = []
        for number, clips in plans:
            rendered = _render_clips(document, clips, options)
            key = f"q{number:02d}"
            image_path = output_dir / f"{asset.stem}_{key}.jpg"
            manifest_path = output_dir / f"{asset.stem}_{key}.json"
            rendered.save(image_path, format="JPEG", quality=options.quality, optimize=True)
            manifest = _manifest(asset, number, document, clips, source_sha256, options, rendered)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append({"question_number": str(number), "image_path": image_path, "manifest_path": manifest_path})
    return results


def _find_anchors(
    document: fitz.Document,
    document_type: str,
    options: SplitOptions,
    bundle_index: int | None = None,
    bundle_count: int = 0,
) -> AnchorSelection:
    candidates = _pdf_text_candidates(document, document_type)
    source = "pdf_text"
    stop: Anchor | None = None
    if document_type == "ms" and bundle_index is not None:
        bundled = _bundled_sequence(candidates, bundle_index, bundle_count)
        anchors, stop = bundled if bundled else ([], None)
    elif document_type == "ms":
        sequences = [
            _contiguous_sequence(
                [item for item in candidates if item.source == candidate_source],
                prefer_latest=True,
                max_x_delta=12.0,
            )
            for candidate_source in ("pdf_heading", "pdf_number_dot", "pdf_number")
        ]
        anchors = max(
            sequences,
            key=lambda sequence: (
                len(sequence),
                sequence[0].page_index if sequence else -1,
                sequence[0].rect.y0 if sequence else -1,
            ),
        )
    else:
        anchors = _contiguous_sequence(candidates)
    if len(anchors) < 2 and bundle_index is None:
        anchors = _contiguous_sequence(candidates, prefer_latest=document_type == "ms")
    if len(anchors) < 2 and bundle_index is None:
        reference_x = next((item.rect.x0 for item in candidates if item.number == 1), None)
        if reference_x is not None:
            candidates.extend(_ocr_number_column_candidates(document, options, reference_x))
            anchors = _contiguous_sequence(candidates, prefer_latest=document_type == "ms")
    if len(anchors) < 2:
        candidates = _ocr_candidates(document, document_type, options)
        source = "ocr"
        if bundle_index is not None:
            reference_sequences = _bundle_sequences(candidates, bundle_count)
            for sequence in reference_sequences:
                candidates.extend(_ocr_number_column_candidates(
                    document,
                    options,
                    sequence[0].rect.x0,
                    allow_q_prefix=True,
                ))
            bundled = _bundled_sequence(candidates, bundle_index, bundle_count)
            anchors, stop = bundled if bundled else ([], None)
        else:
            anchors = _contiguous_sequence(candidates, prefer_latest=document_type == "ms")
        reference_x = next((item.rect.x0 for item in candidates if item.number == 1), None)
        if len(anchors) < 2 and reference_x is not None and bundle_index is None:
            candidates.extend(_ocr_number_column_candidates(document, options, reference_x))
            anchors = _contiguous_sequence(candidates, prefer_latest=document_type == "ms")
    if len(anchors) < 2 or anchors[0].number != 1:
        hint = " Install the project RapidOCR dependencies for scanned historic papers." if source == "ocr" else ""
        raise RuntimeError(f"trusted STEP question sequence was not found.{hint}")
    expected_count = _declared_question_count(document)
    if expected_count and len(anchors) != expected_count:
        raise RuntimeError(f"STEP paper declares {expected_count} questions but {len(anchors)} were found")
    return AnchorSelection(tuple(anchors), stop)


def _pdf_text_candidates(document: fitz.Document, document_type: str) -> list[Anchor]:
    candidates: list[Anchor] = []
    heading_re = re.compile(r"(?:question|solution(?:\s+to)?(?:\s+question)?)\s+(\d{1,2})\b", re.IGNORECASE)
    for page_index, page in enumerate(document):
        if document_type == "ms":
            for block in page.get_text("blocks", sort=True):
                match = heading_re.search(" ".join(str(block[4]).split()))
                if match:
                    candidates.append(Anchor(int(match.group(1)), page_index, fitz.Rect(block[:4]), "pdf_heading"))
        words = page.get_text("words", sort=True)
        for word_index, word in enumerate(words):
            question_match = None
            heading_word_match = None
            if document_type == "ms":
                number_match = re.fullmatch(r"(\d{1,2})(?:\.|\([ivx]+\))?", word[4], re.IGNORECASE)
                question_match = re.fullmatch(r"(?:S(?:I{1,3})-\d{4}/)?Q(\d{1,2})", word[4], re.IGNORECASE)
                heading_word_match = re.fullmatch(r"Question(\d{1,2})\.?", word[4], re.IGNORECASE)
                if word[4].lower() == "question" and word_index + 1 < len(words):
                    following_word = words[word_index + 1]
                    paired_match = re.fullmatch(r"(\d{1,2})\.?", following_word[4])
                    if paired_match and abs(following_word[1] - word[1]) <= 5.0:
                        rect = fitz.Rect(word[:4]) | fitz.Rect(following_word[:4])
                        candidates.append(Anchor(int(paired_match.group(1)), page_index, rect, "pdf_heading_word"))
                number_match = heading_word_match or question_match or number_match
            else:
                number_match = re.fullmatch(r"(\d{1,2})", word[4])
            left_limit = min(150.0, page.rect.width * 0.3) if document_type == "ms" else min(110.0, page.rect.width * 0.22)
            if number_match and word[0] <= left_limit:
                if document_type == "ms" and heading_word_match:
                    source = "pdf_heading_word"
                elif document_type == "ms" and question_match:
                    source = "pdf_question_number"
                else:
                    source = "pdf_number_dot" if word[4].endswith(".") else "pdf_number"
                candidates.append(Anchor(int(number_match.group(1)), page_index, fitz.Rect(word[:4]), source))
    return candidates


def _ocr_candidates(document: fitz.Document, document_type: str, options: SplitOptions) -> list[Anchor]:
    candidates: list[Anchor] = []
    for page_index, page in enumerate(document):
        for line in _ocr_page_lines(document, page_index, options.ocr_dpi):
            clean = line.text
            match = re.match(r"^(?:Q(?:uestion)?\s*)?(\d{1,2})(?:[.)]|\s|$|(?=[A-Za-z(]))", clean, re.IGNORECASE)
            if not match:
                continue
            left = line.rect.x0
            if left > min(120.0, page.rect.width * 0.24):
                continue
            candidates.append(Anchor(int(match.group(1)), page_index, line.rect, "ocr"))
    return candidates


def _ocr_page_lines(document: fitz.Document, page_index: int, dpi: int) -> tuple[OCRLine, ...]:
    key = (_document_cache_key(document), page_index, dpi)
    cached = _OCR_PAGE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("scanned STEP paper requires RapidOCR and ONNX Runtime") from exc
    page = document[page_index]
    scale = dpi / 72.0
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    try:
        result = _rapidocr()(image, use_det=True, use_cls=True, use_rec=True)
    except Exception as exc:
        raise RuntimeError(f"RapidOCR failed: {exc}") from exc
    lines: list[OCRLine] = []
    if result.txts and result.boxes is not None:
        for text, box in zip(result.txts, result.boxes):
            clean = str(text).strip()
            if not clean:
                continue
            lines.append(OCRLine(clean, fitz.Rect(
                float(min(point[0] for point in box)) / scale,
                float(min(point[1] for point in box)) / scale,
                float(max(point[0] for point in box)) / scale,
                float(max(point[1] for point in box)) / scale,
            )))
    cached = tuple(lines)
    _OCR_PAGE_CACHE[key] = cached
    return cached


def _document_cache_key(document: fitz.Document) -> object:
    try:
        stat = Path(document.name).stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    except (OSError, TypeError, ValueError):
        return str(document.name)


def _ocr_number_column_candidates(
    document: fitz.Document,
    options: SplitOptions,
    reference_x: float,
    *,
    allow_q_prefix: bool = False,
) -> list[Anchor]:
    cache_key = (_document_cache_key(document), options.ocr_dpi, round(reference_x, 1), allow_q_prefix)
    cached = _OCR_COLUMN_CACHE.get(cache_key)
    if cached is not None:
        return list(cached)
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    scale = options.ocr_dpi / 72.0
    candidates: list[Anchor] = []
    for page_index, page in enumerate(document):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
        left = max(0, int((reference_x - 8.0) * scale))
        right = min(pixmap.width, int((reference_x + (28.0 if allow_q_prefix else 18.0)) * scale))
        gray = cv2.cvtColor(image[:, left:right], cv2.COLOR_RGB2GRAY)
        ink = gray < 180
        active_rows = np.flatnonzero(ink.sum(axis=1) >= 2)
        if not len(active_rows):
            continue
        groups: list[tuple[int, int]] = []
        start = previous = int(active_rows[0])
        for row in active_rows[1:]:
            row = int(row)
            if row > previous + 1:
                groups.append((start, previous + 1))
                start = row
            previous = row
        groups.append((start, previous + 1))
        for top, bottom in groups:
            height_pt = (bottom - top) / scale
            y0 = top / scale
            if not 4.0 <= height_pt <= 16.0 or not 25.0 <= y0 <= page.rect.height - 30.0:
                continue
            crop_top = max(0, int(top - 5 * scale))
            crop_bottom = min(pixmap.height, int(bottom + 6 * scale))
            result = _rapidocr()(image[crop_top:crop_bottom, left:right], use_det=False, use_cls=False, use_rec=True)
            if not result.txts or not result.scores:
                continue
            text = result.txts[0].strip()
            match = (
                re.match(r"^(?:Q\s*)?(\d{1,2})(?:\D|$)", text, re.IGNORECASE)
                if allow_q_prefix
                else re.fullmatch(r"(\d{1,2})", text)
            )
            if not match or float(result.scores[0]) < 0.8:
                continue
            number = int(match.group(1))
            if 1 <= number <= 20:
                candidates.append(Anchor(
                    number,
                    page_index,
                    fitz.Rect(reference_x - 8.0, y0, reference_x + (28.0 if allow_q_prefix else 18.0), bottom / scale),
                    "ocr_question_column" if allow_q_prefix else "ocr_column",
                ))
    _OCR_COLUMN_CACHE[cache_key] = tuple(candidates)
    return candidates


def _contiguous_sequence(
    candidates: list[Anchor],
    *,
    prefer_latest: bool = False,
    max_x_delta: float = 30.0,
) -> list[Anchor]:
    ordered = sorted(candidates, key=lambda item: (item.page_index, item.rect.y0, item.rect.x0))
    starts = [item for item in ordered if item.number == 1]
    best: list[Anchor] = []
    for first in starts:
        sequence = [first]
        expected = 2
        for item in ordered:
            if (item.page_index, item.rect.y0, item.rect.x0) <= (first.page_index, first.rect.y0, first.rect.x0):
                continue
            if item.number == expected and abs(item.rect.x0 - first.rect.x0) <= max_x_delta:
                sequence.append(item)
                expected += 1
        if len(sequence) > len(best) or (
            prefer_latest
            and len(sequence) == len(best)
            and sequence
            and best
            and (sequence[0].page_index, sequence[0].rect.y0) > (best[0].page_index, best[0].rect.y0)
        ):
            best = sequence
    return best


def _bundled_sequence(
    candidates: list[Anchor],
    bundle_index: int,
    bundle_count: int,
) -> tuple[list[Anchor], Anchor | None] | None:
    sequences = _bundle_sequences(candidates, bundle_count)
    if len(sequences) != bundle_count:
        return None
    anchors = sequences[bundle_index]
    stop = sequences[bundle_index + 1][0] if bundle_index + 1 < len(sequences) else None
    return anchors, stop


def _bundle_sequences(candidates: list[Anchor], bundle_count: int) -> list[list[Anchor]]:
    candidates_by_source: list[list[Anchor]] = []
    def source_group(candidate: Anchor) -> str:
        if candidate.source.startswith("ocr"):
            return "ocr"
        if candidate.source.startswith("pdf_number"):
            return "pdf_number"
        return candidate.source

    source_groups = sorted({source_group(candidate) for candidate in candidates})
    for source in source_groups:
        source_candidates = [candidate for candidate in candidates if source_group(candidate) == source]
        for first in [candidate for candidate in source_candidates if candidate.number == 1]:
            sequence = _sequence_from_first(
                source_candidates,
                first,
                max_x_delta=30.0 if source.startswith("ocr") else 12.0,
            )
            if len(sequence) >= 2:
                candidates_by_source.append(sequence)
    if not candidates_by_source:
        return []
    longest = max(map(len, candidates_by_source))
    eligible = [sequence for sequence in candidates_by_source if len(sequence) >= longest - 2]
    eligible.sort(key=lambda sequence: (sequence[0].page_index, sequence[0].rect.y0))
    best: tuple[tuple[int, int, int], list[list[Anchor]]] | None = None

    def select_from(offset: int, selected: list[list[Anchor]]) -> None:
        nonlocal best
        if len(selected) == bundle_count:
            lengths = [len(sequence) for sequence in selected]
            if max(lengths) - min(lengths) > 2:
                return
            page_span = sum(sequence[-1].page_index - sequence[0].page_index for sequence in selected)
            score = (min(lengths), sum(lengths), -page_span)
            if best is None or score > best[0]:
                best = (score, selected.copy())
            return
        for index in range(offset, len(eligible)):
            sequence = eligible[index]
            if selected and (
                sequence[0].page_index,
                sequence[0].rect.y0,
            ) <= (
                selected[-1][-1].page_index,
                selected[-1][-1].rect.y0,
            ):
                continue
            select_from(index + 1, [*selected, sequence])

    select_from(0, [])
    if best is None:
        return []
    sequences = best[1]
    sequences.sort(key=lambda sequence: (sequence[0].page_index, sequence[0].rect.y0))
    return sequences


def _sequence_from_first(candidates: list[Anchor], first: Anchor, *, max_x_delta: float) -> list[Anchor]:
    sequence = [first]
    expected = 2
    for item in sorted(candidates, key=lambda anchor: (anchor.page_index, anchor.rect.y0, anchor.rect.x0)):
        if (item.page_index, item.rect.y0, item.rect.x0) <= (first.page_index, first.rect.y0, first.rect.x0):
            continue
        if item.number == expected and abs(item.rect.x0 - first.rect.x0) <= max_x_delta:
            sequence.append(item)
            expected += 1
    return sequence


def _declared_question_count(document: fitz.Document) -> int | None:
    front_text = " ".join(document[index].get_text("text") for index in range(min(2, len(document))))
    match = re.search(r"there\s+are\s+(\d{1,2})\s+questions", front_text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _crop_plans(
    document: fitz.Document,
    anchors: list[Anchor],
    options: SplitOptions,
    stop: Anchor | None = None,
) -> list[tuple[int, list[tuple[int, fitz.Rect]]]]:
    plans: list[tuple[int, list[tuple[int, fitz.Rect]]]] = []
    for index, anchor in enumerate(anchors):
        following = anchors[index + 1] if index + 1 < len(anchors) else stop
        last_page = following.page_index if following else len(document) - 1
        clips: list[tuple[int, fitz.Rect]] = []
        for page_index in range(anchor.page_index, last_page + 1):
            page = document[page_index]
            if page_index > anchor.page_index and _is_blank_page(page):
                continue
            top = anchor.rect.y0 - options.top_padding if page_index == anchor.page_index else 32.0
            if following and page_index == following.page_index:
                if page_index == anchor.page_index:
                    bottom = following.rect.y0 - options.top_padding
                else:
                    break
            else:
                bottom = _content_bottom(page, top, options.bottom_padding)
            rect = fitz.Rect(options.horizontal_margin, max(0.0, top), page.rect.width - options.horizontal_margin, min(page.rect.height, bottom))
            if rect.height > 8:
                clips.append((page_index, rect))
        if not clips:
            raise RuntimeError(f"STEP question {anchor.number} produced no trusted crop regions")
        plans.append((anchor.number, clips))
    return plans


def _is_blank_page(page: fitz.Page) -> bool:
    text = " ".join(page.get_text("text").upper().split())
    return "BLANK PAGE" in text or (not text and not page.get_images(full=True))


def _content_bottom(page: fitz.Page, top: float, padding: float) -> float:
    bottoms = [word[3] for word in page.get_text("words") if top <= word[1] < page.rect.height - 55]
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect and rect.y1 >= top and rect.y0 < page.rect.height - 45:
            bottoms.append(rect.y1)
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            if rect.y1 >= top:
                bottoms.append(min(rect.y1, page.rect.height - 45))
    return min(page.rect.height - 45, max(bottoms, default=page.rect.height - 55) + padding)


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
    number: int,
    document: fitz.Document,
    clips: list[tuple[int, fitz.Rect]],
    source_sha256: str,
    options: SplitOptions,
    rendered: Image.Image,
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
        "question_number": str(number),
        "source_stem": asset.stem,
        "page_start": clips[0][0] + 1,
        "page_end": clips[-1][0] + 1,
        "document_type": asset.document_type,
        "cutter": "step_admissions_geometry_v1",
        "crop_regions": regions,
    }
    if asset.document_type == "qp":
        content = _normalize_text("\n".join(document[page_index].get_text("text", clip=rect, sort=True) for page_index, rect in clips))
        content_source = "pdf_text"
        warning = ""
        if _text_is_unreliable(content):
            content = _ocr_clip_text(document, clips, options)
            if content:
                warning = ""
            else:
                content, warning = _ocr_text(rendered)
            content_source = "ocr" if content else "ocr_unavailable"
        manifest["content"] = content
        manifest["content_source"] = content_source
        if warning:
            manifest["content_warning"] = warning
    return manifest


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _text_is_unreliable(text: str) -> bool:
    meaningful = [character for character in text if not character.isspace()]
    if not meaningful or "\ufffd" in text:
        return True
    suspicious = sum(1 for character in meaningful if character in {"□", "�"} or 0xE000 <= ord(character) <= 0xF8FF)
    return len(meaningful) >= 3 and suspicious / len(meaningful) > 0.12


def _ocr_text(image: Image.Image) -> tuple[str, str]:
    try:
        import numpy as np

        result = _rapidocr()(np.asarray(image.convert("RGB")), use_det=True, use_cls=True, use_rec=True)
        return _normalize_text("\n".join(result.txts or ())), ""
    except Exception as exc:
        return "", f"OCR fallback failed: {exc}"


def _ocr_clip_text(document: fitz.Document, clips: list[tuple[int, fitz.Rect]], options: SplitOptions) -> str:
    selected: list[str] = []
    for page_index, clip in clips:
        for line in _ocr_page_lines(document, page_index, options.ocr_dpi):
            center = fitz.Point((line.rect.x0 + line.rect.x1) / 2, (line.rect.y0 + line.rect.y1) / 2)
            if clip.contains(center):
                selected.append(line.text)
    return _normalize_text("\n".join(selected))


@lru_cache(maxsize=1)
def _rapidocr():
    try:
        import onnxruntime as ort
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError("RapidOCR and ONNX Runtime are required for scanned STEP papers") from exc
    use_cuda = "CUDAExecutionProvider" in ort.get_available_providers()
    if use_cuda and hasattr(ort, "preload_dlls"):
        try:
            nvidia_root = Path(ort.__file__).resolve().parent.parent / "nvidia"
            if os.name == "nt" and nvidia_root.exists():
                bin_dirs = sorted(nvidia_root.glob("*/bin"))
                for bin_dir in bin_dirs:
                    _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(bin_dir)))
                os.environ["PATH"] = os.pathsep.join(str(path) for path in bin_dirs) + os.pathsep + os.environ.get("PATH", "")
            ort.preload_dlls(directory="")
        except Exception:
            use_cuda = False
    return RapidOCR(params={"EngineConfig.onnxruntime.use_cuda": use_cuda})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
