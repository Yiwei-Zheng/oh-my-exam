from __future__ import annotations

from pathlib import Path

import pymupdf


def build_question_answer_pdf(question_image: Path, answer_image: Path) -> bytes:
    """Combine the pre-rendered question and answer into one portable PDF."""
    output = pymupdf.open()
    try:
        for image_path in (question_image, answer_image):
            with pymupdf.open(image_path) as image:
                with pymupdf.open("pdf", image.convert_to_pdf()) as page_pdf:
                    output.insert_pdf(page_pdf)
        return output.tobytes(garbage=4, deflate=True)
    finally:
        output.close()
