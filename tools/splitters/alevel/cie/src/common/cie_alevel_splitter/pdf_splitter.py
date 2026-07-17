from __future__ import annotations

from pathlib import Path

from cie_alevel_splitter.cleaning import detect_question_number, is_mostly_blank, normalize_text
from cie_alevel_splitter.models import QuestionSlice


def split_pdf_by_question(pdf_path: Path, output_dir: Path) -> list[QuestionSlice]:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError("PDF splitting requires pypdf. Install it with: python -m pip install pypdf") from exc

    reader = PdfReader(str(pdf_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    groups: list[tuple[str, int, int, str]] = []
    current_number: str | None = None
    current_start = 0
    current_text: list[str] = []

    for index, page in enumerate(reader.pages):
        text = normalize_text(page.extract_text() or "")
        if is_mostly_blank(text):
            continue
        detected = detect_question_number(text)
        if detected and current_number is not None and detected != current_number:
            groups.append((current_number, current_start, index - 1, "\n\n".join(current_text)))
            current_start = index
            current_text = [text]
            current_number = detected
        else:
            if current_number is None:
                current_number = detected or "unknown"
                current_start = index
            current_text.append(text)

    if current_number is not None:
        groups.append((current_number, current_start, len(reader.pages) - 1, "\n\n".join(current_text)))

    if len(groups) <= 1 and len(reader.pages) > 1:
        groups = []
        for index, page in enumerate(reader.pages):
            text = normalize_text(page.extract_text() or "")
            if is_mostly_blank(text):
                continue
            groups.append((str(len(groups) + 1), index, index, text))

    slices: list[QuestionSlice] = []
    for question_number, page_start, page_end, text in groups:
        safe_number = question_number.zfill(2) if question_number.isdigit() else question_number
        out_pdf = output_dir / f"{pdf_path.stem}_q{safe_number}.pdf"
        writer = PdfWriter()
        for page_index in range(page_start, page_end + 1):
            writer.add_page(reader.pages[page_index])
        with out_pdf.open("wb") as fh:
            writer.write(fh)
        slices.append(
            QuestionSlice(
                question_number=question_number,
                source_stem=pdf_path.stem,
                pdf_path=out_pdf,
                page_start=page_start + 1,
                page_end=page_end + 1,
                content=text,
            )
        )
    return slices

