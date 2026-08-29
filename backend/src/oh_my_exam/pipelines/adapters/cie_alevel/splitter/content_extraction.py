from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz
    from PIL import Image as PILImage


@dataclass(frozen=True)
class ContentExtraction:
    content: str
    source: str
    warning: str = ""


def extract_content_from_fitz_clips(
    document: "fitz.Document",
    clips: list[tuple[int, "fitz.Rect"]],
    rendered_image: "PILImage.Image | None" = None,
) -> ContentExtraction:
    pdf_text = _normalize_text(
        "\n".join(
            document[page_index].get_text("text", clip=clip, sort=True)
            for page_index, clip in clips
        )
    )
    if not _looks_unreliable(pdf_text):
        return ContentExtraction(pdf_text, "pdf_text")

    ocr = _ocr_image(rendered_image) if rendered_image is not None else ContentExtraction("", "ocr_unavailable", "no rendered image available for OCR")
    if ocr.content:
        return ocr
    if pdf_text:
        return ContentExtraction(pdf_text, "pdf_text_unreliable", ocr.warning or "PDF text looked unreliable and OCR produced no text")
    return ContentExtraction("", "ocr_unavailable", ocr.warning or "PDF text extraction produced no text and OCR is unavailable")


def extraction_payload(extraction: ContentExtraction) -> dict[str, object]:
    payload: dict[str, object] = {
        "content": extraction.content,
        "content_source": extraction.source,
    }
    if extraction.warning:
        payload["content_warning"] = extraction.warning
    return payload


def extract_content_from_text_or_image(text: str, image_path: Path | None = None) -> ContentExtraction:
    normalized = _normalize_text(text)
    if not _looks_unreliable(normalized):
        return ContentExtraction(normalized, "pdf_text")
    if image_path is None:
        if normalized:
            return ContentExtraction(normalized, "pdf_text_unreliable", "PDF text looked unreliable and no image was available for OCR")
        return ContentExtraction("", "ocr_unavailable", "PDF text extraction produced no text and no image was available for OCR")
    try:
        from PIL import Image
    except ImportError:
        if normalized:
            return ContentExtraction(normalized, "pdf_text_unreliable", "Pillow is not installed, so OCR image loading is unavailable")
        return ContentExtraction("", "ocr_unavailable", "Pillow is not installed, so OCR image loading is unavailable")
    try:
        with Image.open(image_path) as image:
            ocr = _ocr_image(image.convert("L"))
    except OSError as exc:
        if normalized:
            return ContentExtraction(normalized, "pdf_text_unreliable", f"OCR image could not be opened: {exc}")
        return ContentExtraction("", "ocr_unavailable", f"OCR image could not be opened: {exc}")
    if ocr.content:
        return ocr
    if normalized:
        return ContentExtraction(normalized, "pdf_text_unreliable", ocr.warning or "PDF text looked unreliable and OCR produced no text")
    return ContentExtraction("", "ocr_unavailable", ocr.warning or "PDF text extraction produced no text and OCR is unavailable")


def normalize_extracted_text(text: str) -> str:
    return _normalize_text(text)


def text_looks_unreliable(text: str) -> bool:
    return _looks_unreliable(text)


def _normalize_text(text: str) -> str:
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _looks_unreliable(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if "\ufffd" in stripped:
        return True
    meaningful = [character for character in stripped if not character.isspace()]
    if not meaningful:
        return True
    suspicious = 0
    for character in meaningful:
        codepoint = ord(character)
        if codepoint < 32 or 0xE000 <= codepoint <= 0xF8FF:
            suspicious += 1
        elif character in {"□", "�"}:
            suspicious += 1
    if len(meaningful) >= 3 and suspicious / len(meaningful) > 0.12:
        return True
    ascii_letters_or_digits = sum(1 for character in meaningful if character.isascii() and character.isalnum())
    printable = sum(1 for character in meaningful if character.isprintable())
    if len(meaningful) >= 8 and ascii_letters_or_digits == 0 and printable / len(meaningful) < 0.75:
        return True
    return False


def _ocr_image(image: "PILImage.Image | None") -> ContentExtraction:
    if image is None:
        return ContentExtraction("", "ocr_unavailable", "no rendered image available for OCR")

    pytesseract_result = _ocr_with_pytesseract(image)
    if pytesseract_result.source != "ocr_unavailable" or pytesseract_result.content:
        return pytesseract_result
    return _ocr_with_tesseract_cli(image)


def _ocr_with_pytesseract(image: "PILImage.Image") -> ContentExtraction:
    try:
        import pytesseract
    except ImportError:
        return ContentExtraction("", "ocr_unavailable", "pytesseract is not installed")
    try:
        text = _normalize_text(pytesseract.image_to_string(image, lang="eng"))
    except Exception as exc:
        return ContentExtraction("", "ocr_unavailable", f"pytesseract OCR failed: {exc}")
    if text:
        return ContentExtraction(text, "ocr")
    return ContentExtraction("", "ocr_unavailable", "pytesseract OCR produced no text")


def _ocr_with_tesseract_cli(image: "PILImage.Image") -> ContentExtraction:
    executable = shutil.which("tesseract")
    if executable is None:
        return ContentExtraction("", "ocr_unavailable", "OCR fallback requires pytesseract or the tesseract executable")
    with tempfile.TemporaryDirectory(prefix="ome_ocr_") as temp_dir_text:
        temp_dir = Path(temp_dir_text)
        image_path = temp_dir / "question.png"
        output_base = temp_dir / "question_ocr"
        image.save(image_path)
        try:
            subprocess.run(
                [executable, str(image_path), str(output_base), "-l", "eng", "--psm", "6"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            message = (exc.stderr or exc.stdout or str(exc)).strip()
            return ContentExtraction("", "ocr_unavailable", f"tesseract OCR failed: {message}")
        text_path = output_base.with_suffix(".txt")
        try:
            text = _normalize_text(text_path.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            return ContentExtraction("", "ocr_unavailable", f"tesseract OCR output could not be read: {exc}")
    if text:
        return ContentExtraction(text, "ocr")
    return ContentExtraction("", "ocr_unavailable", "tesseract OCR produced no text")
