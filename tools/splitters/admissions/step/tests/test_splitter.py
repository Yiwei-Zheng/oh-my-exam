from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

import step_admissions_splitter.cutter as cutter
from step_admissions_splitter.cutter import split_asset
from step_admissions_splitter.models import load_asset
from step_admissions_splitter.pipeline import discover_downloaded


def test_split_text_step_paper_and_write_packer_compatible_sidecars(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    pdf_path = raw_root / "ocr/admissions/step/2021/archive/step_2021_s2_qp.pdf"
    pdf_path.parent.mkdir(parents=True)
    document = fitz.open()
    cover = document.new_page()
    cover.insert_text((72, 100), "There are 2 questions in this paper.")
    page = document.new_page()
    page.insert_text((52, 80), "1  Prove that x is positive.")
    page.insert_text((52, 280), "2  Evaluate the integral.")
    document.save(pdf_path)
    document.close()
    pdf_path.with_suffix(".json").write_text(
        json.dumps({"source_url": "https://example.test/step.pdf", "source_pdf_sha256": "abc"}),
        encoding="utf-8",
    )

    assert discover_downloaded(raw_root) == [pdf_path]
    outputs = split_asset(load_asset(pdf_path), tmp_path / "processed")

    assert [item["question_number"] for item in outputs] == ["1", "2"]
    first = json.loads(Path(outputs[0]["manifest_path"]).read_text(encoding="utf-8"))
    assert first["source_stem"] == "step_2021_s2_qp"
    assert first["document_type"] == "qp"
    assert first["content_source"] == "pdf_text"
    assert "Prove that x is positive" in first["content"]
    assert first["crop_regions"][0]["source_pdf"] == "https://example.test/step.pdf"


def test_split_solution_question_headings(tmp_path: Path) -> None:
    pdf_path = tmp_path / "step_2022_s3_ms.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((70, 80), "Question 1")
    page.insert_text((70, 120), "A complete solution.")
    page.insert_text((70, 300), "Question 2")
    page.insert_text((70, 340), "Another solution.")
    document.save(pdf_path)
    document.close()

    outputs = split_asset(load_asset(pdf_path), tmp_path / "processed")

    assert [item["question_number"] for item in outputs] == ["1", "2"]
    manifest = json.loads(Path(outputs[0]["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["document_type"] == "ms"
    assert "content" not in manifest


@pytest.mark.parametrize("mark_heading", ["{number}.", "{number}"])
def test_combined_report_and_mark_scheme_prefers_later_complete_sequence(tmp_path: Path, mark_heading: str) -> None:
    pdf_path = tmp_path / "step_2022_s2_ms.pdf"
    document = fitz.open()
    for number in (1, 2):
        page = document.new_page()
        page.insert_text((70, 80), f"Question {number}")
        page.insert_text((70, 120), f"Examiner report content {number}.")
    for number in (1, 2):
        page = document.new_page()
        page.insert_text((70, 80), mark_heading.format(number=number))
        page.insert_text((70, 120), f"Mark scheme content {number}.")
        if number == 1:
            page.insert_text((90, 300), "2")
    document.save(pdf_path)
    document.close()

    outputs = split_asset(load_asset(pdf_path), tmp_path / "processed")

    first = json.loads(Path(outputs[0]["manifest_path"]).read_text(encoding="utf-8"))
    second = json.loads(Path(outputs[1]["manifest_path"]).read_text(encoding="utf-8"))
    assert first["page_start"] == 3
    assert first["page_end"] == 3
    assert second["page_start"] == 4


def test_split_bundled_solutions_selects_only_requested_step_paper(tmp_path: Path) -> None:
    document = fitz.open()
    for paper in (1, 2, 3):
        page = document.new_page()
        page.insert_text((70, 80), "Q1")
        page.insert_text((70, 120), f"STEP {paper} solution one")
        page.insert_text((70, 300), "Q2")
        page.insert_text((70, 340), f"STEP {paper} solution two")
    pdf_bytes = document.tobytes()
    document.close()

    for paper in (1, 2, 3):
        pdf_path = tmp_path / f"step_2017_s{paper}_ms.pdf"
        pdf_path.write_bytes(pdf_bytes)
        pdf_path.with_suffix(".json").write_text(
            json.dumps({"contains_papers": [1, 2, 3]}),
            encoding="utf-8",
        )
        outputs = split_asset(load_asset(pdf_path), tmp_path / "processed")
        first = json.loads(Path(outputs[0]["manifest_path"]).read_text(encoding="utf-8"))
        second = json.loads(Path(outputs[1]["manifest_path"]).read_text(encoding="utf-8"))
        assert (first["page_start"], second["page_end"]) == (paper, paper)


def test_full_page_ocr_resets_detection_after_recognition_only_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeOutput:
        txts = ("1 Test",)
        boxes = (((10, 10), (40, 10), (40, 20), (10, 20)),)

    class StatefulEngine:
        use_det = True

        def __call__(self, _image, *, use_det=None, use_cls=None, use_rec=None):
            if use_det is not None:
                self.use_det = use_det
            return FakeOutput() if self.use_det else type("TextRecOutput", (), {"txts": ("1",), "scores": (1.0,)})()

    engine = StatefulEngine()
    engine(None, use_det=False, use_cls=False, use_rec=True)
    monkeypatch.setattr(cutter, "_rapidocr", lambda: engine)
    cutter._OCR_PAGE_CACHE.clear()

    pdf_path = tmp_path / "ocr.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()
    with fitz.open(pdf_path) as document:
        lines = cutter._ocr_page_lines(document, 0, 72)

    assert [line.text for line in lines] == ["1 Test"]
    assert engine.use_det is True


def test_bundled_ocr_sequence_accepts_column_recovery_from_same_section() -> None:
    candidates = []
    for paper, page in enumerate((0, 10, 20), start=1):
        for number in range(1, 7):
            if paper == 2 and number == 5:
                continue
            candidates.append(cutter.Anchor(number, page + number, fitz.Rect(70, 80, 90, 92), "ocr"))
    candidates.append(cutter.Anchor(5, 15, fitz.Rect(70, 80, 98, 92), "ocr_question_column"))

    sequences = cutter._bundle_sequences(candidates, 3)

    assert [len(sequence) for sequence in sequences] == [6, 6, 6]


def test_bundled_sequence_rejects_incomplete_short_sections() -> None:
    candidates = []
    for paper, count in enumerate((13, 3, 2)):
        for number in range(1, count + 1):
            candidates.append(cutter.Anchor(number, paper * 20 + number, fitz.Rect(70, 80, 90, 92), "pdf_number"))

    assert cutter._bundle_sequences(candidates, 3) == []
