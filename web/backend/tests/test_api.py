from __future__ import annotations

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pymupdf

from oh_my_exam_server.config import Settings
from oh_my_exam_server.main import create_app
from oh_my_exam_server.paper_store import FileSystemPaperStore, PaperNotFoundError


def _create_subject_database(path: Path) -> None:
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE database_info (
                qualification TEXT, exam_board TEXT, course_code TEXT, course_display_name TEXT
            );
            INSERT INTO database_info VALUES ('admissions', 'uat', 'engaa', 'ENGAA');
            CREATE TABLE papers (
                id INTEGER PRIMARY KEY, qp_stem TEXT, ms_stem TEXT, qp_url TEXT, ms_url TEXT
            );
            INSERT INTO papers VALUES (
                1, 'engaa_2023_s1_qp', 'engaa_2023_s1_ms', 'https://example.test/qp', 'https://example.test/ms'
            );
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY, paper_id INTEGER, local_question_key TEXT, question_number TEXT
            );
            INSERT INTO questions VALUES (7, 1, 'q07', '7');
            CREATE TABLE question_texts (question_id INTEGER PRIMARY KEY, content TEXT);
            INSERT INTO question_texts VALUES (7, 'Find the acceleration of the particle.');
            CREATE TABLE crop_regions (
                question_id INTEGER, source_type INTEGER, region_order INTEGER, page_index INTEGER,
                x0 REAL, y0 REAL, x1 REAL, y1 REAL, render_dpi INTEGER, join_gap_px INTEGER,
                post_left INTEGER, post_top INTEGER, post_right INTEGER, post_bottom INTEGER
            );
            INSERT INTO crop_regions VALUES (7, 0, 0, 1, 0, 0, 200, 50, 180, 0, NULL, NULL, NULL, NULL);
            INSERT INTO crop_regions VALUES (7, 1, 0, 1, 0, 0, 200, 50, 180, 0, NULL, NULL, NULL, NULL);
            """
        )


def _client(tmp_path: Path) -> TestClient:
    database_root = tmp_path / "databases"
    paper_root = tmp_path / "raw_papers"
    _create_subject_database(database_root / "admissions" / "uat" / "uat_admissions_engaa.sqlite")
    paper_root.mkdir(parents=True)
    _write_pdf(paper_root / "engaa_2023_s1_qp.pdf", "Question page", "Find the acceleration")
    _write_pdf(paper_root / "engaa_2023_s1_ms.pdf", "Answer page", "Acceleration is 2")
    settings = Settings(tmp_path, database_root, paper_root)
    return TestClient(create_app(settings))


def _write_pdf(path: Path, first_page: str, second_page: str) -> None:
    document = pymupdf.open()
    try:
        document.new_page(width=200, height=100).insert_text((10, 20), first_page)
        document.new_page(width=200, height=100).insert_text((10, 20), second_page)
        document.save(path)
    finally:
        document.close()


def test_catalog_question_and_local_pdf_endpoints(tmp_path: Path) -> None:
    client = _client(tmp_path)

    exams = client.get("/api/v1/exams")
    assert exams.status_code == 200
    assert exams.json()[0]["id"] == "admissions:uat:engaa"
    assert exams.json()[0]["question_count"] == 1

    questions = client.get("/api/v1/exams/admissions:uat:engaa/questions", params={"query": "acceleration"})
    assert questions.status_code == 200
    assert questions.json()[0]["id"] == 7

    question = client.get("/api/v1/exams/admissions:uat:engaa/questions/7")
    assert question.status_code == 200
    assert question.json()["crop_regions"][0]["render_dpi"] == 180

    question_pdf = client.get("/api/v1/exams/admissions:uat:engaa/questions/7/question.pdf")
    assert question_pdf.status_code == 200
    assert question_pdf.headers["content-type"] == "application/pdf"
    assert question_pdf.headers["content-disposition"] == 'inline; filename="engaa_2023_s1_qp_q07.pdf"'
    with pymupdf.open(stream=question_pdf.content, filetype="pdf") as cropped:
        assert cropped.page_count == 1
        assert cropped[0].rect.width == 200
        assert cropped[0].rect.height == 50
        assert "Find the acceleration" in cropped[0].get_text()

    answer_pdf = client.get("/api/v1/exams/admissions:uat:engaa/questions/7/answer.pdf")
    assert answer_pdf.status_code == 200
    with pymupdf.open(stream=answer_pdf.content, filetype="pdf") as cropped:
        assert "Acceleration is 2" in cropped[0].get_text()

    paper = client.get("/api/v1/exams/admissions:uat:engaa/papers/1/question")
    assert paper.status_code == 200
    assert paper.headers["content-type"] == "application/pdf"
    assert paper.content.startswith(b"%PDF")

    paper_range = client.get(
        "/api/v1/exams/admissions:uat:engaa/papers/1/question",
        headers={"Range": "bytes=0-3"},
    )
    assert paper_range.status_code == 206
    assert paper_range.content == b"%PDF"

    unsupported_kind = client.get("/api/v1/exams/admissions:uat:engaa/papers/1/upstream-url")
    assert unsupported_kind.status_code == 404


def test_placeholders_are_explicit(tmp_path: Path) -> None:
    client = _client(tmp_path)

    capabilities = client.get("/api/v1/capabilities").json()
    assert capabilities["catalog"]["status"] == "ready"
    assert capabilities["authentication"]["status"] == "placeholder"
    assert capabilities["tmua_data"]["status"] == "missing"

    response = client.post("/api/v1/math/evaluate", json={"input": "x + x"})
    assert response.status_code == 501
    assert response.json()["capability"] == "math_harness"


def test_paper_store_rejects_globs_and_paths(tmp_path: Path) -> None:
    store = FileSystemPaperStore(tmp_path)
    for unsafe_stem in ("../paper", "*.pdf", "folder/paper"):
        try:
            store.find_by_stem(unsafe_stem)
        except PaperNotFoundError:
            continue
        raise AssertionError(f"unsafe stem was accepted: {unsafe_stem}")
