from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from exam_packer import PackOptions, discover_metadata_courses, pack_subject_database
from exam_packer.models import MetadataCourse


def test_packer_writes_compact_search_and_crop_sqlite(tmp_path: Path) -> None:
    metadata_root = tmp_path / "metadata"
    output_dir = tmp_path / "databases"
    _write_sidecar(
        metadata_root,
        "cie/a_level/9231/2022/w22/11/qp/9231_w22_qp_11_q01_b.json",
        document_type="qp",
        question_number="1(b)",
        content="Find the value of the constant.",
        crop_regions=[
            _region("9231_w22_qp_11", "qp", order=0, rect=(1, 2, 3, 4)),
            _region("9231_w22_qp_11", "qp", order=1, rect=(5, 6, 7, 8), join_gap_before_px=12),
        ],
    )
    _write_sidecar(
        metadata_root,
        "cie/a_level/9231/2022/w22/11/ms/9231_w22_ms_11_q01_b.json",
        document_type="ms",
        question_number="1(b)",
        crop_regions=[
            _region(
                "9231_w22_ms_11",
                "ms",
                order=0,
                rect=(10, 20, 30, 40),
                post_render_crop_px={
                    "coordinate_space": "rendered_clip_pixels",
                    "unit": "px",
                    "left": 4,
                    "top": 5,
                    "right": 200,
                    "bottom": 250,
                },
            )
        ],
    )

    summary = pack_subject_database(
        PackOptions(
            metadata_root=metadata_root,
            output_dir=output_dir,
            qualification="a_level",
            exam_board="cie",
            course_code="9231",
        )
    )
    db_path = output_dir / "cie_a_level_9231.sqlite"

    assert summary.metadata_count == 2
    assert summary.matched_pairs == 1
    assert summary.papers_written == 1
    assert summary.questions_written == 1
    assert summary.crop_regions_written == 3
    assert summary.question_texts_written == 1
    assert db_path.exists()

    with closing(sqlite3.connect(db_path)) as conn:
        assert _table_names(conn).isdisjoint(
            {
                "qualifications",
                "exam_boards",
                "courses",
                "question_sources",
                "paper_documents",
                "metadata_fields",
                "schema_migrations",
                "question_fts",
                "question_fts_config",
            }
        )
        assert conn.execute(
            "SELECT qualification, exam_board, course_code, course_display_name FROM database_info"
        ).fetchone() == ("a_level", "cie", "9231", "9231")
        database_info_columns = {row[1] for row in conn.execute("PRAGMA table_info(database_info)")}
        assert {"schema_version", "database_version", "created_at", "updated_at"}.isdisjoint(database_info_columns)
        question_columns = {row[1] for row in conn.execute("PRAGMA table_info(questions)")}
        assert {
            "question_key",
            "content",
            "parent_question_id",
            "question_label",
            "subquestion_label",
            "global_question_key",
            "qp_metadata_path",
            "qp_image_path",
            "ms_metadata_path",
            "ms_image_path",
        }.isdisjoint(question_columns)
        question = conn.execute(
            """
            SELECT p.qp_stem, p.ms_stem, q.local_question_key, q.question_number
            FROM questions q
            JOIN papers p ON p.id = q.paper_id
            """
        ).fetchone()
        assert question == (
            "9231_w22_qp_11",
            "9231_w22_ms_11",
            "q01_b",
            "1(b)",
        )
        paper_columns = {row[1] for row in conn.execute("PRAGMA table_info(papers)")}
        assert {"qp_url", "ms_url", "source_url"}.isdisjoint(paper_columns)
        question_text = conn.execute("SELECT question_id, content FROM question_texts").fetchone()
        assert question_text == (1, "Find the value of the constant.")
        crop_rows = conn.execute(
            """
            SELECT source_type, region_order, page_index, x0, y0, x1, y1,
                   render_dpi, join_gap_px, post_left, post_bottom
            FROM crop_regions
            ORDER BY source_type, region_order
            """
        ).fetchall()
        assert crop_rows[0] == (0, 0, 0, 1.0, 2.0, 3.0, 4.0, 150, 0, None, None)
        assert crop_rows[1] == (0, 1, 0, 5.0, 6.0, 7.0, 8.0, 150, 12, None, None)
        assert crop_rows[2] == (1, 0, 0, 10.0, 20.0, 30.0, 40.0, 150, 0, 4, 250)

    second = pack_subject_database(
        PackOptions(
            metadata_root=metadata_root,
            output_dir=output_dir,
            qualification="a_level",
            exam_board="cie",
            course_code="9231",
        )
    )
    assert second.questions_written == 1
    assert second.crop_regions_written == 3
    assert second.question_texts_written == 1


def test_packer_reports_only_and_duplicate_sources(tmp_path: Path) -> None:
    metadata_root = tmp_path / "metadata"
    output_dir = tmp_path / "databases"
    _write_sidecar(metadata_root, "only_qp/9231_w22_qp_11_q01.json", document_type="qp")
    _write_sidecar(metadata_root, "only_ms/9231_w22_ms_11_q02.json", document_type="ms")
    _write_sidecar(metadata_root, "dup_a/9231_w22_qp_11_q03.json", document_type="qp")
    _write_sidecar(metadata_root, "dup_b/9231_w22_qp_11_q03.json", document_type="qp")
    _write_sidecar(metadata_root, "amb_qp_a/9231_w22_qp_11_q04.json", document_type="qp")
    _write_sidecar(metadata_root, "amb_qp_b/9231_w22_qp_11_q04.json", document_type="qp")
    _write_sidecar(metadata_root, "amb_ms_a/9231_w22_ms_11_q04.json", document_type="ms")
    _write_sidecar(metadata_root, "amb_ms_b/9231_w22_ms_11_q04.json", document_type="ms")

    summary = pack_subject_database(
        PackOptions(
            metadata_root=metadata_root,
            output_dir=output_dir,
            qualification="a_level",
            exam_board="cie",
            course_code="9231",
            dry_run=True,
        )
    )

    assert summary.metadata_count == 8
    assert summary.only_qp == 2
    assert summary.only_ms == 1
    assert summary.duplicate_qp == 2
    assert summary.duplicate_ms == 1
    assert summary.ambiguous_match == 1
    assert not (output_dir / "cie_a_level_9231.sqlite").exists()


def test_ms_sidecar_with_content_is_rejected_by_schema(tmp_path: Path) -> None:
    metadata_root = tmp_path / "metadata"
    output_dir = tmp_path / "databases"
    _write_sidecar(
        metadata_root,
        "cie/a_level/9231/2022/w22/11/ms/9231_w22_ms_11_q01.json",
        document_type="ms",
        content="Old mock answer text.",
    )

    summary = pack_subject_database(
        PackOptions(
            metadata_root=metadata_root,
            output_dir=output_dir,
            qualification="a_level",
            exam_board="cie",
            course_code="9231",
            dry_run=True,
        )
    )

    assert summary.metadata_count == 0
    assert any("unexpected metadata fields" in warning and "content" in warning for warning in summary.warnings)


def test_loader_rejects_legacy_filename_and_accepts_underscore_component(tmp_path: Path) -> None:
    metadata_root = tmp_path / "metadata"
    output_dir = tmp_path / "databases"
    _write_sidecar(
        metadata_root,
        "cie/a_level/9709/2003/s03/1/ms/9709_s03_ms_q01.json",
        document_type="ms",
        source_stem="9709_s03_ms",
    )
    _write_sidecar(
        metadata_root,
        "cie/a_level/9709/2015/s15/41_2/qp/9709_s15_qp_41_2_q01.json",
        document_type="qp",
        source_stem="9709_s15_qp_41_2",
        content="Find x.",
    )

    summary = pack_subject_database(
        PackOptions(
            metadata_root=metadata_root,
            output_dir=output_dir,
            qualification="a_level",
            exam_board="cie",
            course_code="9709",
        )
    )

    assert summary.metadata_count == 1
    assert any("unified CIE A-Level splitter schema" in warning for warning in summary.warnings)
    with closing(sqlite3.connect(output_dir / "cie_a_level_9709.sqlite")) as conn:
        stems = {row[0] for row in conn.execute("SELECT qp_stem FROM papers")}
        assert stems == {"9709_s15_qp_41_2"}


def test_uat_admissions_sidecars_are_discovered_and_packed(tmp_path: Path) -> None:
    metadata_root = tmp_path / "metadata"
    output_dir = tmp_path / "databases"
    base = metadata_root / "uat" / "admissions" / "engaa" / "2016" / "archive" / "s1"
    _write_uat_sidecar(base / "qp" / "engaa_2016_s1_qp_q01.json", document_type="qp")
    _write_uat_sidecar(base / "ms" / "engaa_2016_s1_ms_q01.json", document_type="ms")

    assert discover_metadata_courses(metadata_root) == [
        MetadataCourse(qualification="admissions", exam_board="uat", course_code="engaa", metadata_count=2)
    ]

    summary = pack_subject_database(
        PackOptions(
            metadata_root=metadata_root,
            output_dir=output_dir,
            qualification="admissions",
            exam_board="uat",
            course_code="engaa",
        )
    )

    assert summary.metadata_count == 2
    assert summary.matched_pairs == 1
    with closing(sqlite3.connect(output_dir / "uat_admissions_engaa.sqlite")) as conn:
        assert conn.execute("SELECT qp_stem, ms_stem FROM papers").fetchone() == (
            "engaa_2016_s1_qp",
            "engaa_2016_s1_ms",
        )
        assert conn.execute("SELECT local_question_key, question_number FROM questions").fetchone() == (
            "q01",
            "1",
        )
        assert conn.execute("SELECT content FROM question_texts").fetchone() == ("Question text",)


def _write_sidecar(
    root: Path,
    relative_path: str,
    *,
    document_type: str,
    question_number: str = "1",
    content: str | None = None,
    crop_regions: list[dict[str, object]] | None = None,
    source_stem: str | None = None,
) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    source_stem = source_stem or "_".join(path.stem.split("_")[:4])
    payload: dict[str, object] = {
        "question_number": question_number,
        "source_stem": source_stem,
        "document_type": document_type,
        "source_url": f"https://example.test/{source_stem}.pdf",
        "crop_regions": crop_regions if crop_regions is not None else [_region(source_stem, document_type, order=0)],
    }
    if document_type == "qp":
        payload["content"] = content or ""
    elif content is not None:
        payload["content"] = content
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    path.with_suffix(".jpg").write_bytes(b"fake image")
    return path


def _write_uat_sidecar(path: Path, *, document_type: str) -> None:
    source_stem = path.stem.rsplit("_q", 1)[0]
    payload: dict[str, object] = {
        "question_number": "1",
        "source_stem": source_stem,
        "page_start": 1,
        "page_end": 1,
        "document_type": document_type,
        "cutter": "uat_admissions_geometry_v1",
        "crop_regions": [
            {
                "order": 0,
                "source_pdf": f"https://example.test/{source_stem}.pdf",
                "page_index": 0,
                "rect": {"x0": 1, "y0": 2, "x1": 3, "y1": 4},
                "render_dpi": 180,
                "join_gap_before_px": 0,
            }
        ],
    }
    if document_type == "qp":
        payload.update({"content": "Question text", "content_source": "pdf_text"})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _region(
    source_stem: str,
    document_type: str,
    *,
    order: int,
    rect: tuple[int, int, int, int] = (1, 2, 3, 4),
    join_gap_before_px: int = 0,
    post_render_crop_px: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "order": order,
        "page_index": 0,
        "rect": {"x0": rect[0], "y0": rect[1], "x1": rect[2], "y1": rect[3]},
        "render_dpi": 150,
        "join_gap_before_px": join_gap_before_px,
        **({"post_render_crop_px": post_render_crop_px} if post_render_crop_px else {}),
    }


def _table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
