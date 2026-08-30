from __future__ import annotations

import hashlib
from functools import lru_cache
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import fitz
from PIL import Image

from oh_my_exam.pipelines.adapters.uat.splitter.models import PaperAsset


@dataclass(frozen=True)
class SplitOptions:
    dpi: int = 180
    quality: int = 90
    horizontal_margin: float = 42.0
    top_padding: float = 4.0
    bottom_padding: float = 8.0
    join_gap_px: int = 20


@dataclass(frozen=True)
class Anchor:
    number: int
    page_index: int
    rect: fitz.Rect


def split_asset(
    asset: PaperAsset,
    processed_root: Path,
    options: SplitOptions | None = None,
    *,
    answer_choices: dict[int, str] | None = None,
) -> list[dict[str, object]]:
    options = options or SplitOptions()
    output_dir = processed_root / asset.output_relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    source_sha256 = asset.source_sha256 or _sha256(asset.pdf_path)
    with fitz.open(asset.pdf_path) as document:
        if asset.document_type == "qp":
            plans = _question_plans(document, options)
        elif asset.source_document_type == "worked_answers":
            plans = _worked_answer_plans(document, options)
        else:
            plans = _answer_key_plans(document)
        if asset.exam == "tmua" and [number for number, _ in plans] != list(range(1, 21)):
            raise RuntimeError(f"TMUA {asset.document_type} did not yield exactly questions 1-20")
        if answer_choices is not None and set(answer_choices) != {number for number, _ in plans}:
            raise RuntimeError("official answer key does not cover the same questions as the worked answers")
        results: list[dict[str, object]] = []
        for number, clips in plans:
            rendered = _render_clips(document, clips, options)
            key = f"q{number:02d}"
            image_path = output_dir / f"{asset.stem}_{key}.jpg"
            json_path = output_dir / f"{asset.stem}_{key}.json"
            rendered.save(image_path, format="JPEG", quality=options.quality, optimize=True)
            manifest = _manifest(
                asset,
                number,
                document,
                clips,
                source_sha256,
                options,
                rendered,
                answer_choice=answer_choices.get(number) if answer_choices else None,
            )
            json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            results.append({"question_number": str(number), "image_path": image_path, "manifest_path": json_path})
    return results


def _question_plans(document: fitz.Document, options: SplitOptions) -> list[tuple[int, list[tuple[int, fitz.Rect]]]]:
    anchors = _find_question_anchors(document)
    plans: list[tuple[int, list[tuple[int, fitz.Rect]]]] = []
    for index, anchor in enumerate(anchors):
        following = anchors[index + 1] if index + 1 < len(anchors) else None
        last_page = following.page_index if following else len(document) - 1
        clips: list[tuple[int, fitz.Rect]] = []
        for page_index in range(anchor.page_index, last_page + 1):
            page = document[page_index]
            if page_index > anchor.page_index and _is_template_page(page):
                continue
            top = anchor.rect.y0 - options.top_padding if page_index == anchor.page_index else 42.0
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
            raise RuntimeError(f"question {anchor.number} produced no trusted crop regions")
        plans.append((anchor.number, clips))
    return plans


def _find_question_anchors(document: fitz.Document) -> list[Anchor]:
    candidates: list[Anchor] = []
    for page_index, page in enumerate(document):
        for word in page.get_text("words", sort=True):
            text = word[4]
            if re.fullmatch(r"\d{1,3}", text) and 40.0 <= word[0] <= 80.0 and 35.0 <= word[1] <= 760.0:
                candidates.append(Anchor(int(text), page_index, fitz.Rect(word[:4])))
    try:
        return _sequential_anchors(candidates)
    except RuntimeError:
        ocr_candidates = _find_question_anchors_with_ocr(document)
        return _sequential_anchors([*candidates, *ocr_candidates], repair_page_gaps=True)


def _sequential_anchors(candidates: list[Anchor], *, repair_page_gaps: bool = False) -> list[Anchor]:
    if not candidates:
        raise RuntimeError("no question numbers found in the official left number column")
    first = next((candidate for candidate in candidates if candidate.number == 1), None)
    if first is None:
        raise RuntimeError("question sequence does not start at 1")
    candidates = [candidate for candidate in candidates if abs(candidate.rect.x0 - first.rect.x0) <= 6.0]
    candidates.sort(key=lambda item: (item.page_index, item.rect.y0, item.number))
    if repair_page_gaps:
        candidates = _repair_page_gaps(candidates)
    expected = 1
    anchors: list[Anchor] = []
    for candidate in candidates:
        if candidate.number == expected:
            anchors.append(candidate)
            expected += 1
    if not anchors or anchors[0].number != 1:
        raise RuntimeError("question sequence does not start at 1")
    return anchors


def _repair_page_gaps(candidates: list[Anchor]) -> list[Anchor]:
    repaired = list(candidates)
    ordered = sorted(candidates, key=lambda item: (item.page_index, item.rect.y0))
    for previous, following in zip(ordered, ordered[1:]):
        number_gap = following.number - previous.number
        page_gap = following.page_index - previous.page_index
        if number_gap <= 1 or number_gap != page_gap:
            continue
        for offset in range(1, number_gap):
            if any(item.number == previous.number + offset for item in repaired):
                continue
            repaired.append(Anchor(
                previous.number + offset,
                previous.page_index + offset,
                fitz.Rect(previous.rect.x0, 54.0, previous.rect.x1, 66.0),
            ))
    return sorted(repaired, key=lambda item: (item.page_index, item.rect.y0, item.number))


def _find_question_anchors_with_ocr(document: fitz.Document) -> list[Anchor]:
    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("legacy question-number detection requires the optional OCR dependencies") from exc
    engine = _rapidocr_engine()
    scale = 1.5
    candidates: list[Anchor] = []
    for page_index, page in enumerate(document):
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
        result = engine(image)
        if result.boxes is None:
            continue
        for box, text in zip(result.boxes, result.txts):
            match = re.match(r"^(\d{1,2})(?:\.|\s|$)", str(text).strip())
            if match is None:
                continue
            x0 = min(float(point[0]) for point in box) / scale
            y0 = min(float(point[1]) for point in box) / scale
            x1 = max(float(point[0]) for point in box) / scale
            y1 = max(float(point[1]) for point in box) / scale
            if 40.0 <= x0 <= 82.0 and 35.0 <= y0 <= 760.0:
                candidates.append(Anchor(int(match.group(1)), page_index, fitz.Rect(x0, y0, x1, y1)))
    return candidates


@lru_cache(maxsize=1)
def _rapidocr_engine():
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError("legacy PDF support requires the optional rapidocr package") from exc
    return RapidOCR(params={"Global.use_cls": False})


def _worked_answer_plans(
    document: fitz.Document,
    options: SplitOptions,
) -> list[tuple[int, list[tuple[int, fitz.Rect]]]]:
    starts: list[tuple[int, int]] = []
    for page_index, page in enumerate(document):
        text = _normalize_text(page.get_text("text", sort=True))
        matches = re.findall(r"(?i)\bquestion\s+(\d{1,2})\b", text)
        if len(matches) == 1:
            starts.append((int(matches[0]), page_index))
    if [number for number, _ in starts] != list(range(1, 21)):
        raise RuntimeError("worked answers do not contain one ordered section for questions 1-20")
    plans: list[tuple[int, list[tuple[int, fitz.Rect]]]] = []
    for index, (number, first_page) in enumerate(starts):
        next_page = starts[index + 1][1] if index + 1 < len(starts) else document.page_count
        clips: list[tuple[int, fitz.Rect]] = []
        for page_index in range(first_page, next_page):
            page = document[page_index]
            page_text = _normalize_text(page.get_text("text", sort=True))
            if number == 20 and page_index > first_page and (
                not page_text
                or re.search(r"(?i)\b(acknowledgements?|blank page)\b", page_text)
            ):
                break
            bottom = _content_bottom(page, 42.0, options.bottom_padding)
            clips.append((page_index, fitz.Rect(42.0, 42.0, page.rect.width - 42.0, bottom)))
        if not clips:
            raise RuntimeError(f"worked answer {number} produced no crop regions")
        plans.append((number, clips))
    return plans


def load_tmua_answer_keys(path: Path) -> dict[str, dict[int, str]]:
    if not path.is_file():
        raise RuntimeError(f"TMUA answer key is missing: {path}")
    rows: list[tuple[int, str, int | None, str | None]] = []
    with fitz.open(path) as document:
        text = "\n".join(page.get_text("text", sort=True) for page in document)
    for line in text.splitlines():
        match = re.fullmatch(r"\s*(\d{1,2})\s+([A-H])(?:\s+(\d{1,2})\s+([A-H]))?\s*", line)
        if match:
            rows.append((int(match.group(1)), match.group(2), int(match.group(3)) if match.group(3) else None, match.group(4)))
    paper_1: dict[int, str] = {}
    paper_2: dict[int, str] = {}
    for number, choice, second_number, second_choice in rows:
        if second_number is not None and second_choice is not None:
            paper_1[number] = choice
            paper_2[second_number] = second_choice
        elif len(paper_1) < 20:
            paper_1[number] = choice
        else:
            paper_2[number] = choice
    expected = set(range(1, 21))
    if set(paper_1) != expected or set(paper_2) != expected:
        raise RuntimeError(f"TMUA answer key did not yield 20 answers for both papers: {path}")
    return {"p1": paper_1, "p2": paper_2}


def _answer_key_plans(document: fitz.Document) -> list[tuple[int, list[tuple[int, fitz.Rect]]]]:
    rows: dict[int, tuple[int, fitz.Rect]] = {}
    for page_index, page in enumerate(document):
        words = page.get_text("words", sort=True)
        numeric_words = [word for word in words if re.fullmatch(r"Q?\d{1,3}", word[4], re.IGNORECASE)]
        for word in numeric_words:
            number = int(word[4].lstrip("Qq"))
            same_row = [
                candidate for candidate in words
                if candidate[0] > word[2]
                and candidate[0] - word[2] < 95
                and abs(candidate[1] - word[1]) < max(3.0, word[3] - word[1])
                and re.fullmatch(r"[A-H]", candidate[4], re.IGNORECASE)
            ]
            if not same_row:
                continue
            answer = min(same_row, key=lambda candidate: candidate[0])
            rows[number] = (page_index, fitz.Rect(word[0] - 5, min(word[1], answer[1]) - 2, answer[2] + 5, max(word[3], answer[3]) + 2))
    if not rows:
        raise RuntimeError("answer key contained no recognizable question/answer rows")
    maximum = max(rows)
    missing = [number for number in range(1, maximum + 1) if number not in rows]
    if missing:
        raise RuntimeError(f"answer key sequence is incomplete: missing {missing[:8]}")
    return [(number, [rows[number]]) for number in range(1, maximum + 1)]


def _is_template_page(page: fitz.Page) -> bool:
    text = " ".join(page.get_text("text", sort=True).upper().split())
    if "BLANK PAGE" in text:
        return True
    without_templates = re.sub(r"(?:PART [A-Z].*|© UCLES \d{4}|\[TURN OVER\]|\b\d{1,3}\b)", "", text).strip()
    return text.startswith("PART ") and len(without_templates) < 24


def _content_bottom(page: fitz.Page, top: float, padding: float) -> float:
    bottoms = [word[3] for word in page.get_text("words") if top <= word[1] < page.rect.height - 55]
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect and rect.y1 >= top and rect.y0 < page.rect.height - 45:
            bottoms.append(rect.y1)
    for image in page.get_images(full=True):
        for rect in page.get_image_rects(image[0]):
            if rect.y1 >= top and rect.y0 < page.rect.height - 45:
                bottoms.append(rect.y1)
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
    *,
    answer_choice: str | None = None,
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
        "cutter": "uat_admissions_geometry_v1",
        "crop_regions": regions,
    }
    if asset.document_type == "qp":
        content = _normalize_text("\n".join(document[page_index].get_text("text", clip=rect, sort=True) for page_index, rect in clips))
        source = "pdf_text"
        warning = ""
        if _text_is_unreliable(content):
            ocr_content, ocr_warning = _ocr(rendered)
            if ocr_content:
                content, source = ocr_content, "ocr"
            else:
                source = "pdf_text_unreliable" if content else "ocr_unavailable"
                warning = ocr_warning or "PDF text was unreliable and OCR produced no text"
        manifest["content"] = content
        manifest["content_source"] = source
        if warning:
            manifest["content_warning"] = warning
    elif answer_choice is not None:
        manifest["answer_choice"] = answer_choice
    return manifest


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _text_is_unreliable(text: str) -> bool:
    meaningful = [character for character in text if not character.isspace()]
    if not meaningful or "\ufffd" in text:
        return True
    suspicious = sum(
        1
        for character in meaningful
        if character in {"□", "�"}
        or 0x80 <= ord(character) <= 0x9F
        or 0xE000 <= ord(character) <= 0xF8FF
        or unicodedata.category(character) == "Cc"
    )
    return len(meaningful) >= 3 and suspicious / len(meaningful) > 0.12


def _ocr(image: Image.Image) -> tuple[str, str]:
    try:
        import numpy as np

        result = _rapidocr_engine()(np.asarray(image.convert("RGB")))
        if result.txts:
            return _normalize_text("\n".join(str(value) for value in result.txts)), ""
    except (ImportError, RuntimeError) as rapid_exc:
        rapid_warning = str(rapid_exc)
    except Exception as rapid_exc:
        rapid_warning = f"RapidOCR failed: {rapid_exc}"
    try:
        import pytesseract
    except ImportError:
        return "", rapid_warning or "OCR fallback requires an optional OCR package"
    try:
        return _normalize_text(pytesseract.image_to_string(image, lang="eng")), ""
    except Exception as exc:
        return "", f"{rapid_warning}; Tesseract OCR failed: {exc}" if rapid_warning else f"OCR fallback failed: {exc}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
