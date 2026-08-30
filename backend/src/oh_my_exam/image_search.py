from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

from PIL import Image, UnidentifiedImageError


MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
STOP_WORDS = {
    "and", "are", "for", "from", "has", "have", "into", "its", "that",
    "the", "then", "this", "using", "was", "what", "when", "where", "which",
    "with", "you", "your",
}


class ImageSearchError(ValueError):
    pass


class OcrUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageText:
    text: str
    source: str


def extract_image_text(data_url: str) -> ImageText:
    media_type, encoded = _split_data_url(data_url)
    if media_type not in SUPPORTED_MEDIA_TYPES:
        raise ImageSearchError("unsupported_image_type")
    try:
        content = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageSearchError("invalid_image_data") from exc
    if not content or len(content) > MAX_IMAGE_BYTES:
        raise ImageSearchError("image_size_invalid")

    try:
        with Image.open(BytesIO(content)) as opened:
            width, height = opened.size
            if width * height > MAX_IMAGE_PIXELS:
                raise ImageSearchError("image_dimensions_too_large")
            image = opened.convert("RGB")
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as exc:
        raise ImageSearchError("invalid_image_data") from exc

    image.thumbnail((2400, 2400))
    rapid_text = _rapidocr_text(image)
    if rapid_text:
        return ImageText(rapid_text, "rapidocr")

    tesseract_text = _pytesseract_text(image)
    if tesseract_text:
        return ImageText(tesseract_text, "tesseract")
    raise OcrUnavailableError("ocr_unavailable")


def image_search_query(text: str) -> str:
    terms = (
        match.casefold()
        for match in re.findall(r"[A-Za-z0-9]+", text)
        if len(match) >= 3
    )
    return " ".join(dict.fromkeys(term for term in terms if term not in STOP_WORDS))[:500]


def _split_data_url(data_url: str) -> tuple[str, str]:
    header, separator, encoded = data_url.partition(",")
    if not separator or not header.startswith("data:") or ";base64" not in header:
        raise ImageSearchError("invalid_image_data")
    return header[5:].split(";", 1)[0].casefold(), encoded


@lru_cache(maxsize=1)
def _rapidocr_engine():
    try:
        from rapidocr import RapidOCR
    except ImportError:
        return None
    return RapidOCR()


def _rapidocr_text(image: Image.Image) -> str:
    engine = _rapidocr_engine()
    if engine is None:
        return ""
    try:
        import numpy as np

        output = engine(np.asarray(image))
    except Exception:
        return ""

    texts = getattr(output, "txts", None)
    if texts is None and isinstance(output, (list, tuple)) and output:
        rows = output[0] or []
        texts = [row[1] for row in rows if len(row) > 1]
    return _normalize_text(" ".join(str(text) for text in (texts or [])))


def _pytesseract_text(image: Image.Image) -> str:
    try:
        import pytesseract

        return _normalize_text(pytesseract.image_to_string(image, lang="eng"))
    except Exception:
        return ""


def _normalize_text(text: str) -> str:
    return " ".join(text.split())
