from __future__ import annotations

import base64
from io import BytesIO

import pytest
from PIL import Image

import oh_my_exam.image_search as image_search
from oh_my_exam.image_search import (
    ImageSearchError,
    extract_image_text,
    image_search_query,
)


def test_extract_image_text_validates_and_runs_ocr(monkeypatch) -> None:
    image = Image.new("RGB", (80, 40), "white")
    stream = BytesIO()
    image.save(stream, format="PNG")
    data_url = "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()
    monkeypatch.setattr(image_search, "_rapidocr_text", lambda _image: "Find acceleration")

    result = extract_image_text(data_url)

    assert result.text == "Find acceleration"
    assert result.source == "rapidocr"


def test_extract_image_text_rejects_non_image_data() -> None:
    with pytest.raises(ImageSearchError, match="unsupported_image_type"):
        extract_image_text("data:text/plain;base64,SGVsbG8=")


def test_image_search_query_removes_common_ocr_words() -> None:
    assert image_search_query("Find the acceleration of the particle") == (
        "find acceleration particle"
    )
