from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping

import pymupdf


class QuestionDocumentError(ValueError):
    pass


def crop_question_pdf(source_path: Path, regions: Iterable[Mapping[str, object]]) -> bytes:
    """Create a compact vector PDF containing one page per question crop region."""

    output = pymupdf.open()
    try:
        with pymupdf.open(source_path) as source:
            for region in regions:
                page_index = _required_int(region, "page_index")
                if page_index < 0 or page_index >= source.page_count:
                    raise QuestionDocumentError(f"crop page is outside source PDF: {page_index}")
                source_page = source[page_index]
                clip = _clip_rect(region).intersect(source_page.rect)
                if clip.is_empty or clip.is_infinite:
                    raise QuestionDocumentError(f"invalid crop rectangle on page {page_index}")
                target = output.new_page(width=clip.width, height=clip.height)
                target.show_pdf_page(target.rect, source, page_index, clip=clip)
        if output.page_count == 0:
            raise QuestionDocumentError("question has no crop regions")
        return output.tobytes(garbage=4, deflate=True)
    finally:
        output.close()


def _clip_rect(region: Mapping[str, object]) -> pymupdf.Rect:
    clip = pymupdf.Rect(
        _required_float(region, "x0"),
        _required_float(region, "y0"),
        _required_float(region, "x1"),
        _required_float(region, "y1"),
    )
    dpi = _optional_float(region.get("render_dpi"))
    post_values = tuple(
        _optional_float(region.get(key))
        for key in ("post_left", "post_top", "post_right", "post_bottom")
    )
    if dpi and dpi > 0 and all(value is not None for value in post_values):
        left, top, right, bottom = (float(value) for value in post_values)
        scale = 72.0 / dpi
        clip = pymupdf.Rect(
            clip.x0 + left * scale,
            clip.y0 + top * scale,
            clip.x0 + right * scale,
            clip.y0 + bottom * scale,
        )
    return clip


def _required_int(region: Mapping[str, object], key: str) -> int:
    value = region.get(key)
    if value is None:
        raise QuestionDocumentError(f"crop region is missing {key}")
    return int(value)


def _required_float(region: Mapping[str, object], key: str) -> float:
    value = _optional_float(region.get(key))
    if value is None:
        raise QuestionDocumentError(f"crop region is missing {key}")
    return value


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
