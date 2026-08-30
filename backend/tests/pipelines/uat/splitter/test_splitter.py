from __future__ import annotations

import json
from pathlib import Path

import fitz

from oh_my_exam.pipelines.adapters.uat.splitter.cutter import SplitOptions, load_tmua_answer_keys, split_asset
from oh_my_exam.pipelines.adapters.uat.splitter.models import PaperAsset, load_asset


def _asset(path: Path, document_type: str) -> PaperAsset:
    return PaperAsset(
        "engaa",
        "2023",
        "s1",
        document_type,
        path,
        "https://example.test/source.pdf",
        "abc123",
        document_type,
    )


def test_question_splitter_writes_stable_sidecars(tmp_path: Path) -> None:
    pdf_path = tmp_path / "engaa_2023_s1_qp.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((51, 75), "1", fontsize=11)
    page.insert_text((75, 75), "First question with choices A B C D", fontsize=11)
    page.insert_text((51, 360), "2", fontsize=11)
    page.insert_text((75, 360), "Second question", fontsize=11)
    page = doc.new_page(width=595, height=842)
    page.insert_text((51, 75), "3", fontsize=11)
    page.insert_text((75, 75), "Third question", fontsize=11)
    doc.save(pdf_path)
    doc.close()

    outputs = split_asset(_asset(pdf_path, "qp"), tmp_path / "processed", SplitOptions(dpi=72))
    assert len(outputs) == 3
    manifest = json.loads(outputs[0]["manifest_path"].read_text(encoding="utf-8"))
    assert set(manifest) == {"question_number", "content", "source_stem", "page_start", "page_end", "document_type", "cutter", "content_source", "crop_regions"}
    assert manifest["question_number"] == "1"
    assert manifest["crop_regions"][0]["source_pdf"] == "https://example.test/source.pdf"


def test_answer_key_splitter_writes_one_ms_per_row(tmp_path: Path) -> None:
    pdf_path = tmp_path / "engaa_2023_s1_ms.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    for number, answer, y in [(1, "B", 120), (2, "D", 140), (3, "A", 160)]:
        page.insert_text((84, y), f"Q{number}", fontsize=10)
        page.insert_text((120, y), answer, fontsize=10)
    doc.save(pdf_path)
    doc.close()

    outputs = split_asset(_asset(pdf_path, "ms"), tmp_path / "processed", SplitOptions(dpi=72))
    assert len(outputs) == 3
    manifest = json.loads(outputs[1]["manifest_path"].read_text(encoding="utf-8"))
    assert "content" not in manifest
    assert manifest["document_type"] == "ms"
    assert manifest["question_number"] == "2"


def test_tmua_worked_answer_filename_normalizes_to_matching_ms_stem(tmp_path: Path) -> None:
    path = tmp_path / "tmua_early_specimen_p2_worked_answers.pdf"

    asset = load_asset(path)

    assert asset.period == "early_specimen"
    assert asset.component == "p2"
    assert asset.document_type == "ms"
    assert asset.source_document_type == "worked_answers"
    assert asset.stem == "tmua_early_specimen_p2_ms"


def test_tmua_answer_key_parser_keeps_paper_columns_separate(tmp_path: Path) -> None:
    path = tmp_path / "tmua_2023_ms.pdf"
    document = fitz.open()
    page = document.new_page(width=400, height=600)
    for number in range(1, 21):
        page.insert_text((40, 40 + number * 20), f"{number} A    {number} H", fontsize=10)
    document.save(path)
    document.close()

    keys = load_tmua_answer_keys(path)

    assert keys["p1"] == {number: "A" for number in range(1, 21)}
    assert keys["p2"] == {number: "H" for number in range(1, 21)}
