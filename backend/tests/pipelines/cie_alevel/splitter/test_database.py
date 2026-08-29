from pathlib import Path
import sqlite3

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.models import PaperAsset, QuestionSlice
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.database import connect, upsert_asset, upsert_mark_scheme_slice, upsert_question_slice


def test_database_ingests_question_and_mark_scheme(tmp_path: Path) -> None:
    db_path = tmp_path / "exam.sqlite3"

    asset = PaperAsset("cie", "a_level", "9702", "Physics", "w24", "qp", "31")
    question = QuestionSlice("1", "9702_w24_qp_31", tmp_path / "q1.pdf", 1, 2, content="Describe the motion.")
    mark = QuestionSlice("1", "9702_w24_ms_31", tmp_path / "m1.pdf", 1, 1)

    with connect(db_path) as conn:
        paper_id = upsert_asset(conn, asset, tmp_path / "source.pdf")
        question_id = upsert_question_slice(conn, paper_id, question)
        upsert_mark_scheme_slice(conn, question_id, mark)
        mark_scheme_count = conn.execute("SELECT COUNT(*) FROM mark_schemes").fetchone()[0]
        point_count = conn.execute("SELECT COUNT(*) FROM marking_points").fetchone()[0]
        content = conn.execute("SELECT content FROM questions WHERE id = ?", (question_id,)).fetchone()[0]

    assert mark_scheme_count == 1
    assert point_count == 0
    assert content == "Describe the motion."


def test_database_ingests_structured_mark_scheme_points(tmp_path: Path) -> None:
    db_path = tmp_path / "exam.sqlite3"

    asset = PaperAsset("cie", "a_level", "9709", "Mathematics", "w24", "qp", "12")
    question = QuestionSlice("1", "9709_w24_qp_12", tmp_path / "q1.jpg", 1, 1)
    mark = QuestionSlice(
        "1",
        "9709_w24_ms_12",
        tmp_path / "m1.jpg",
        1,
        1,
        mark_scheme_points=(
            {
                "score": 1,
                "type": "M",
                "marking_point": "(1+5x+10x^2)(1-12x+60x^2) leading to 60-60+10",
                "supplement": "3 products required",
            },
        ),
    )

    with connect(db_path) as conn:
        paper_id = upsert_asset(conn, asset, tmp_path / "source.pdf")
        question_id = upsert_question_slice(conn, paper_id, question)
        upsert_mark_scheme_slice(conn, question_id, mark)
        structured_json = conn.execute("SELECT structured_json FROM mark_schemes").fetchone()[0]
        point = conn.execute("SELECT mark_type, marker, text FROM marking_points").fetchone()

    assert '"supplement": "3 products required"' in structured_json
    assert point == ("M", "M1", "(1+5x+10x^2)(1-12x+60x^2) leading to 60-60+10")


def test_database_migrates_existing_questions_table_with_content_column(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY,
                paper_id INTEGER NOT NULL,
                question_number TEXT NOT NULL,
                question_pdf_path TEXT,
                page_start INTEGER,
                page_end INTEGER
            );
            """
        )

    with connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}

    assert "content" in columns
