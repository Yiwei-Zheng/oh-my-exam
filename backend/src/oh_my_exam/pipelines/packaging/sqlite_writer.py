from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from oh_my_exam.pipelines.packaging.models import MetadataRecord, PackOptions, PackSummary
from oh_my_exam.pipelines.packaging.schema import migrate


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> bool:
        result = super().__exit__(exc_type, exc_value, traceback)
        self.close()
        return result


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, factory=ClosingConnection)
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn)
    return conn


def write_records(db_path: Path, options: PackOptions, records: list[MetadataRecord], summary: PackSummary) -> PackSummary:
    with connect(db_path) as conn:
        _insert_database_info(conn, options)
        for record in records:
            paper_id = _upsert_paper(conn, record)
            question_id = _upsert_question(conn, paper_id, record)
            _insert_search_text(conn, question_id, record)
            _replace_question_image(conn, question_id, record, options.metadata_root)
            _replace_crop_regions(conn, question_id, record)
        conn.commit()
        summary.papers_written = _count(conn, "papers")
        summary.questions_written = _count(conn, "questions")
        summary.crop_regions_written = _count(conn, "crop_regions")
        summary.question_texts_written = _count(conn, "question_texts")
        summary.question_images_written = _count(conn, "question_images")
    return summary


def _insert_database_info(conn: sqlite3.Connection, options: PackOptions) -> None:
    conn.execute(
        """
        INSERT INTO database_info (id, qualification, exam_board, course_code, course_display_name)
        VALUES (1, ?, ?, ?, ?)
        """,
        (
            options.qualification,
            options.exam_board,
            options.course_code,
            options.course_display_name or options.course_code,
        ),
    )


def _upsert_paper(conn: sqlite3.Connection, record: MetadataRecord) -> int:
    qp_stem = _source_stem_for(record, "QP")
    ms_stem = _source_stem_for(record, "MS")
    conn.execute(
        """
        INSERT INTO papers (qp_stem, ms_stem)
        VALUES (?, ?)
        ON CONFLICT(qp_stem) DO UPDATE SET
            ms_stem = excluded.ms_stem
        """,
        (qp_stem, ms_stem),
    )
    row = conn.execute("SELECT id FROM papers WHERE qp_stem = ?", (qp_stem,)).fetchone()
    if row is None:
        raise RuntimeError("failed to upsert paper")
    return int(row[0])


def _upsert_question(conn: sqlite3.Connection, paper_id: int, record: MetadataRecord) -> int:
    question_number = record.metadata.get("question_number")
    conn.execute(
        """
        INSERT INTO questions (paper_id, local_question_key, question_number)
        VALUES (?, ?, ?)
        ON CONFLICT(paper_id, local_question_key) DO UPDATE SET
            question_number = CASE
                WHEN excluded.question_number != '' THEN excluded.question_number
                ELSE questions.question_number
            END
        """,
        (paper_id, record.local_question_key, str(question_number) if question_number is not None else ""),
    )
    row = conn.execute(
        "SELECT id FROM questions WHERE paper_id = ? AND local_question_key = ?",
        (paper_id, record.local_question_key),
    ).fetchone()
    if row is None:
        raise RuntimeError("failed to upsert question")
    return int(row[0])


def _insert_search_text(conn: sqlite3.Connection, question_id: int, record: MetadataRecord) -> None:
    if record.source_type != "QP":
        return
    content = record.metadata.get("content")
    if content is None or str(content).strip() == "":
        return
    conn.execute(
        """
        INSERT INTO question_texts (question_id, content)
        VALUES (?, ?)
        ON CONFLICT(question_id) DO UPDATE SET
            content = excluded.content
        """,
        (question_id, str(content)),
    )


def _replace_question_image(
    conn: sqlite3.Connection,
    question_id: int,
    record: MetadataRecord,
    metadata_root: Path,
) -> None:
    source_type = _source_type_code(record.source_type)
    conn.execute(
        "DELETE FROM question_images WHERE question_id = ? AND source_type = ?",
        (question_id, source_type),
    )
    if record.image_path is None:
        raise ValueError(f"pre-rendered question image is missing for {record.metadata_path}")
    root = metadata_root.resolve()
    image_path = record.image_path.resolve()
    if not image_path.is_relative_to(root) or not image_path.is_file():
        raise ValueError(f"question image is outside metadata root or missing: {record.image_path}")
    conn.execute(
        """
        INSERT INTO question_images (
            question_id, source_type, storage_key, original_filename, size_bytes
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            question_id,
            source_type,
            image_path.relative_to(root).as_posix(),
            image_path.name,
            image_path.stat().st_size,
        ),
    )


def _replace_crop_regions(conn: sqlite3.Connection, question_id: int, record: MetadataRecord) -> None:
    source_type = _source_type_code(record.source_type)
    conn.execute("DELETE FROM crop_regions WHERE question_id = ? AND source_type = ?", (question_id, source_type))
    for index, region in enumerate(record.crop_regions):
        if not isinstance(region, dict):
            continue
        rect = region.get("rect") if isinstance(region.get("rect"), dict) else {}
        post_crop = region.get("post_render_crop_px") if isinstance(region.get("post_render_crop_px"), dict) else {}
        _insert_crop_region(conn, question_id, source_type, index, region, rect, post_crop)


def _insert_crop_region(
    conn: sqlite3.Connection,
    question_id: int,
    source_type: int,
    index: int,
    region: dict[str, Any],
    rect: dict[str, Any],
    post_crop: dict[str, Any],
) -> None:
    columns = {
        "question_id": question_id,
        "source_type": source_type,
        "region_order": int(region.get("order", index)),
        "page_index": _optional_int(region.get("page_index")),
        "x0": _optional_float(rect.get("x0")),
        "y0": _optional_float(rect.get("y0")),
        "x1": _optional_float(rect.get("x1")),
        "y1": _optional_float(rect.get("y1")),
        "render_dpi": _optional_int(region.get("render_dpi")),
        "join_gap_px": _optional_int(region.get("join_gap_before_px")) or 0,
        "post_left": _optional_int(post_crop.get("left")),
        "post_top": _optional_int(post_crop.get("top")),
        "post_right": _optional_int(post_crop.get("right")),
        "post_bottom": _optional_int(post_crop.get("bottom")),
    }
    placeholders = ", ".join("?" for _ in columns)
    conn.execute(
        f"INSERT INTO crop_regions ({', '.join(columns)}) VALUES ({placeholders})",
        tuple(columns.values()),
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _source_stem_for(record: MetadataRecord, source_type: str) -> str:
    marker = f"_{record.source_type.lower()}_"
    replacement = f"_{source_type.lower()}_"
    if marker in record.source_stem:
        return record.source_stem.replace(marker, replacement, 1)
    suffix = f"_{record.source_type.lower()}"
    if record.source_stem.endswith(suffix):
        return f"{record.source_stem[:-len(suffix)]}_{source_type.lower()}"
    raise ValueError(f"source stem does not contain document marker: {record.source_stem}")


def _source_type_code(source_type: str) -> int:
    if source_type == "QP":
        return 0
    if source_type == "MS":
        return 1
    raise ValueError(f"unknown source_type: {source_type}")
