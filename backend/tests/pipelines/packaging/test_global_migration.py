from __future__ import annotations

from pathlib import Path
import sqlite3

import pymupdf

from oh_my_exam.pipelines.packaging.answer_extraction import _looks_garbled, _normalize_markdown_text, extract_answer_markdown
from oh_my_exam.pipelines.packaging.global_migration import GlobalMigrationOptions, migrate_portable_catalogs


def test_migrates_portable_database_without_urls_or_hashes(tmp_path: Path) -> None:
    database_root = tmp_path / "databases"
    paper_root = tmp_path / "raw_papers"
    source_path = database_root / "admissions" / "uat" / "uat_admissions_tmua.sqlite"
    source_path.parent.mkdir(parents=True)
    paper_dir = paper_root / "uat" / "admissions" / "tmua" / "2023"
    paper_dir.mkdir(parents=True)
    _write_pdf(paper_dir / "tmua_2023_s1_qp.pdf", "Question")
    _write_pdf(paper_dir / "tmua_2023_s1_ms.pdf", "Answer: x = 2")
    _write_portable_database(source_path)
    image_root = tmp_path / "processed_questions"
    image_dir = image_root / "uat" / "admissions" / "tmua" / "2023"
    image_dir.mkdir(parents=True)
    question_image = image_dir / "tmua_2023_s1_qp_q01.jpg"
    answer_image = image_dir / "tmua_2023_s1_ms_q01.jpg"
    question_image.write_bytes(b"question jpeg")
    answer_image.write_bytes(b"answer jpeg")
    with sqlite3.connect(source_path) as conn:
        conn.executescript(
            """
            CREATE TABLE question_images (
                question_id INTEGER, source_type INTEGER, storage_key TEXT,
                original_filename TEXT, size_bytes INTEGER
            );
            """
        )
        conn.executemany(
            "INSERT INTO question_images VALUES (7, ?, ?, ?, ?)",
            [
                (0, "uat/admissions/tmua/2023/tmua_2023_s1_qp_q01.jpg", question_image.name, question_image.stat().st_size),
                (1, "uat/admissions/tmua/2023/tmua_2023_s1_ms_q01.jpg", answer_image.name, answer_image.stat().st_size),
            ],
        )

    output_path = database_root / "global_exam_catalog.sqlite"
    summary = migrate_portable_catalogs(
        GlobalMigrationOptions(
            database_root,
            paper_root,
            output_path,
            strip_legacy_urls=True,
            image_root=image_root,
        )
    )

    assert summary.source_databases == 1
    assert summary.questions == 1
    assert summary.answers == 1
    extraction = extract_answer_markdown(output_path, paper_root)
    assert extraction.answers_seen == 1
    assert extraction.versions_written == 1
    assert extraction.empty_answers == 0
    with sqlite3.connect(output_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"paper_documents", "question_images", "answers", "features", "question_embeddings"} <= table_names
        all_columns = {
            row[1]
            for table in table_names
            if not table.startswith("sqlite_")
            for row in conn.execute(f"PRAGMA table_info({table})")
        }
        assert "source_url" not in all_columns
        assert "upstream_url" not in all_columns
        assert "sha256" not in all_columns
        assert conn.execute(
            "SELECT stable_key FROM questions"
        ).fetchone()[0] == "admissions:uat:tmua:tmua_2023_s1_qp:q01"
        assert conn.execute(
            "SELECT role, storage_key FROM paper_documents ORDER BY role"
        ).fetchall() == [
            ("answer_key", "uat/admissions/tmua/2023/tmua_2023_s1_ms.pdf"),
            ("question_paper", "uat/admissions/tmua/2023/tmua_2023_s1_qp.pdf"),
        ]
        assert conn.execute(
            "SELECT image_kind, storage_key FROM question_images ORDER BY image_kind"
        ).fetchall() == [
            ("answer", "uat/admissions/tmua/2023/tmua_2023_s1_ms_q01.jpg"),
            ("question", "uat/admissions/tmua/2023/tmua_2023_s1_qp_q01.jpg"),
        ]
        assert conn.execute(
            "SELECT answer_kind, authority, status FROM answers"
        ).fetchone() == ("answer_key", "official", "draft")
        assert "Answer: x = 2" in conn.execute(
            "SELECT markdown FROM answer_versions"
        ).fetchone()[0]
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    with sqlite3.connect(source_path) as conn:
        source_columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
        assert {"qp_url", "ms_url", "source_url"}.isdisjoint(source_columns)


def test_migration_requires_explicit_overwrite(tmp_path: Path) -> None:
    database_root = tmp_path / "databases"
    paper_root = tmp_path / "raw_papers"
    source_path = database_root / "subject.sqlite"
    database_root.mkdir()
    paper_root.mkdir()
    _write_portable_database(source_path, include_regions=False)
    output_path = database_root / "global.sqlite"

    migrate_portable_catalogs(GlobalMigrationOptions(database_root, paper_root, output_path))

    try:
        migrate_portable_catalogs(GlobalMigrationOptions(database_root, paper_root, output_path))
    except FileExistsError:
        pass
    else:
        raise AssertionError("existing global database was overwritten without --overwrite")


def test_answer_markdown_removes_known_page_boilerplate() -> None:
    assert _normalize_markdown_text("physicsandmathstutor.com\n") == ""
    assert _normalize_markdown_text("Step II Hints and Answers June 2005\nx = 2\n") == "x = 2"
    assert _normalize_markdown_text("June 2005\nReport on the Components taken in June\nx = 2") == "x = 2"


def test_answer_extraction_detects_further_math_symbol_font_mojibake() -> None:
    assert _looks_garbled("I□ = ⅓mr² and \x98 is an invalid mapped glyph")
    assert _looks_garbled("Use the value င in the next line")
    assert not _looks_garbled("M1: ∫ x² dx = ⅓x³ + c")


def _write_portable_database(path: Path, include_regions: bool = True) -> None:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE database_info (
                qualification TEXT, exam_board TEXT, course_code TEXT, course_display_name TEXT
            );
            INSERT INTO database_info VALUES ('admissions', 'uat', 'tmua', 'TMUA');
            CREATE TABLE papers (
                id INTEGER PRIMARY KEY, qp_stem TEXT, ms_stem TEXT, qp_url TEXT, ms_url TEXT
            );
            INSERT INTO papers VALUES (
                1, 'tmua_2023_s1_qp', 'tmua_2023_s1_ms',
                'https://example.test/question.pdf', 'https://example.test/answer.pdf'
            );
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY, paper_id INTEGER, local_question_key TEXT, question_number TEXT
            );
            INSERT INTO questions VALUES (7, 1, 'q01', '1');
            CREATE TABLE question_texts (question_id INTEGER PRIMARY KEY, content TEXT);
            INSERT INTO question_texts VALUES (7, 'Find the value of x.');
            CREATE TABLE crop_regions (
                question_id INTEGER, source_type INTEGER, region_order INTEGER, page_index INTEGER,
                x0 REAL, y0 REAL, x1 REAL, y1 REAL, render_dpi INTEGER, join_gap_px INTEGER,
                post_left INTEGER, post_top INTEGER, post_right INTEGER, post_bottom INTEGER
            );
            """
        )
        if include_regions:
            conn.executescript(
                """
                INSERT INTO crop_regions VALUES (7, 0, 0, 1, 0, 0, 200, 50, 180, 0, NULL, NULL, NULL, NULL);
                INSERT INTO crop_regions VALUES (7, 1, 0, 2, 0, 0, 200, 50, 180, 0, NULL, NULL, NULL, NULL);
                """
            )


def _write_pdf(path: Path, text: str) -> None:
    document = pymupdf.open()
    try:
        page = document.new_page(width=200, height=100)
        page.insert_text((10, 20), text)
        document.new_page(width=200, height=100).insert_text((10, 20), text)
        document.new_page(width=200, height=100).insert_text((10, 20), text)
        document.save(path)
    finally:
        document.close()
