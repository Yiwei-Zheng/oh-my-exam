from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3

from oh_my_exam.pipelines.packaging.global_schema import migrate_global_catalog


@dataclass(frozen=True)
class GlobalMigrationOptions:
    database_root: Path
    paper_root: Path
    output_path: Path
    overwrite: bool = False
    strip_legacy_urls: bool = False
    image_root: Path | None = None


@dataclass
class GlobalMigrationSummary:
    source_databases: int = 0
    portable_databases_sanitized: int = 0
    exam_programs: int = 0
    papers: int = 0
    paper_documents: int = 0
    questions: int = 0
    question_texts: int = 0
    question_regions: int = 0
    question_images: int = 0
    answers: int = 0
    answer_regions: int = 0

    def as_lines(self) -> list[str]:
        return [f"{name}={value}" for name, value in vars(self).items()]


def migrate_portable_catalogs(options: GlobalMigrationOptions) -> GlobalMigrationSummary:
    database_root = options.database_root.resolve()
    paper_root = options.paper_root.resolve()
    image_root = (
        options.image_root.resolve()
        if options.image_root is not None
        else paper_root.parent / "processed_questions"
    )
    output_path = options.output_path.resolve()
    if not database_root.is_dir():
        raise ValueError(f"database root does not exist: {database_root}")
    if not paper_root.is_dir():
        raise ValueError(f"paper root does not exist: {paper_root}")
    if output_path.exists() and not options.overwrite:
        raise FileExistsError(f"output database already exists: {output_path}")

    source_paths = [
        path.resolve()
        for path in sorted(database_root.rglob("*.sqlite"))
        if path.resolve() != output_path and path.name != "global_exam_catalog.sqlite"
    ]
    if not source_paths:
        raise ValueError(f"no portable SQLite databases found under: {database_root}")

    paper_index = _build_paper_index(paper_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_name(f"{output_path.name}.building")
    if temporary_path.exists():
        temporary_path.unlink()

    summary = GlobalMigrationSummary()
    try:
        with closing(sqlite3.connect(temporary_path)) as target:
            target.execute("PRAGMA foreign_keys = ON")
            migrate_global_catalog(target)
            for source_path in source_paths:
                _migrate_source(
                    target,
                    source_path,
                    paper_root,
                    image_root,
                    paper_index,
                    summary,
                )
            target.commit()
            violations = target.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise RuntimeError(f"foreign key validation failed: {violations[:5]}")
            integrity = target.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise RuntimeError(f"SQLite integrity check failed: {integrity}")
            _fill_summary_counts(target, summary)
        temporary_path.replace(output_path)
        if options.strip_legacy_urls:
            summary.portable_databases_sanitized = strip_portable_url_columns(source_paths)
    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()
        raise
    return summary


def strip_portable_url_columns(database_paths: list[Path]) -> int:
    sanitized = 0
    for database_path in database_paths:
        with closing(sqlite3.connect(database_path)) as conn:
            columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(papers)")}
            removable = [column for column in ("qp_url", "ms_url", "source_url") if column in columns]
            if not removable:
                continue
            for column in removable:
                conn.execute(f"ALTER TABLE papers DROP COLUMN {column}")
            conn.commit()
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            if integrity is None or integrity[0] != "ok":
                raise RuntimeError(f"SQLite integrity check failed after sanitizing {database_path}: {integrity}")
            sanitized += 1
    return sanitized


def _migrate_source(
    target: sqlite3.Connection,
    source_path: Path,
    paper_root: Path,
    image_root: Path,
    paper_index: dict[str, Path],
    summary: GlobalMigrationSummary,
) -> None:
    source_uri = f"{source_path.as_uri()}?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True)) as source:
        source.row_factory = sqlite3.Row
        info = source.execute(
            "SELECT qualification, exam_board, course_code, course_display_name FROM database_info LIMIT 1"
        ).fetchone()
        if info is None:
            raise ValueError(f"database_info is missing from {source_path}")
        qualification = str(info["qualification"]).strip()
        exam_board = str(info["exam_board"]).strip()
        course_code = str(info["course_code"]).strip()
        display_name = str(info["course_display_name"]).strip() or course_code.upper()
        program_id = _upsert_program(target, exam_board, qualification, course_code, display_name)

        paper_map: dict[int, int] = {}
        paper_stable_keys: dict[int, str] = {}
        document_map: dict[tuple[int, int], int] = {}
        for row in source.execute("SELECT id, qp_stem, ms_stem FROM papers ORDER BY id"):
            source_paper_id = int(row["id"])
            qp_stem = str(row["qp_stem"]).strip()
            ms_stem = str(row["ms_stem"]).strip()
            paper_id = _insert_paper(target, program_id, qualification, exam_board, course_code, qp_stem)
            paper_map[source_paper_id] = paper_id
            paper_stable_keys[source_paper_id] = f"{qualification}:{exam_board}:{course_code}:{qp_stem}"
            qp_path = paper_index.get(qp_stem.casefold())
            if qp_path is not None:
                document_map[(source_paper_id, 0)] = _insert_document(
                    target, paper_id, "question_paper", qp_path, paper_root
                )
            ms_path = paper_index.get(ms_stem.casefold()) if ms_stem else None
            if ms_path is not None:
                answer_role = _answer_role(exam_board, course_code, ms_path.stem)
                document_map[(source_paper_id, 1)] = _insert_document(
                    target, paper_id, answer_role, ms_path, paper_root
                )

        question_map: dict[int, int] = {}
        question_papers: dict[int, int] = {}
        question_rows = source.execute(
            "SELECT id, paper_id, local_question_key, question_number FROM questions ORDER BY paper_id, id"
        ).fetchall()
        paper_positions: dict[int, int] = {}
        for row in question_rows:
            source_question_id = int(row["id"])
            source_paper_id = int(row["paper_id"])
            position = paper_positions.get(source_paper_id, 0) + 1
            paper_positions[source_paper_id] = position
            paper_id = paper_map[source_paper_id]
            local_key = str(row["local_question_key"])
            paper_key = paper_stable_keys[source_paper_id]
            stable_key = f"{paper_key}:{local_key}"
            cursor = target.execute(
                """
                INSERT INTO questions (
                    paper_id, stable_key, local_key, question_number, sort_order
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (paper_id, stable_key, local_key, str(row["question_number"]), position),
            )
            question_map[source_question_id] = int(cursor.lastrowid)
            question_papers[source_question_id] = source_paper_id

        for row in source.execute("SELECT question_id, content FROM question_texts ORDER BY question_id"):
            content = str(row["content"])
            if content.strip():
                target.execute(
                    "INSERT INTO question_texts (question_id, text_kind, language, content) VALUES (?, 'search', 'en', ?)",
                    (question_map[int(row["question_id"])], content),
                )

        if _table_exists(source, "question_images"):
            for row in source.execute(
                """
                SELECT question_id, source_type, storage_key, original_filename, size_bytes
                FROM question_images
                ORDER BY question_id, source_type
                """
            ):
                source_question_id = int(row["question_id"])
                storage_key = str(row["storage_key"])
                image_path = _resolve_image_path(image_root, storage_key)
                actual_size = image_path.stat().st_size
                expected_size = int(row["size_bytes"])
                if actual_size != expected_size:
                    raise ValueError(
                        f"question image size changed: {storage_key} "
                        f"(catalog={expected_size}, actual={actual_size})"
                    )
                target.execute(
                    """
                    INSERT INTO question_images (
                        question_id, image_kind, storage_key, original_filename, size_bytes
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        question_map[source_question_id],
                        "question" if int(row["source_type"]) == 0 else "answer",
                        storage_key,
                        str(row["original_filename"]),
                        actual_size,
                    ),
                )

        answer_map: dict[int, int] = {}
        region_rows = source.execute(
            """
            SELECT question_id, source_type, region_order, page_index, x0, y0, x1, y1,
                   render_dpi, join_gap_px, post_left, post_top, post_right, post_bottom
            FROM crop_regions
            ORDER BY question_id, source_type, region_order
            """
        ).fetchall()
        for row in region_rows:
            source_question_id = int(row["question_id"])
            source_type = int(row["source_type"])
            source_paper_id = question_papers[source_question_id]
            document_id = document_map.get((source_paper_id, source_type))
            if document_id is None:
                raise ValueError(
                    f"crop region references a missing local PDF in {source_path.name}: "
                    f"question={source_question_id}, source_type={source_type}"
                )
            values = _region_values(row)
            question_id = question_map[source_question_id]
            if source_type == 0:
                target.execute(
                    """
                    INSERT INTO question_regions (
                        question_id, document_id, region_order, page_index, x0, y0, x1, y1,
                        render_dpi, join_gap_px, post_left, post_top, post_right, post_bottom
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (question_id, document_id, *values),
                )
                continue
            answer_id = answer_map.get(source_question_id)
            if answer_id is None:
                answer_kind = _answer_kind(exam_board, course_code, document_id, target)
                cursor = target.execute(
                    """
                    INSERT INTO answers (question_id, source_document_id, answer_kind, authority, status)
                    VALUES (?, ?, ?, 'official', 'source_only')
                    """,
                    (question_id, document_id, answer_kind),
                )
                answer_id = int(cursor.lastrowid)
                answer_map[source_question_id] = answer_id
            target.execute(
                """
                INSERT INTO answer_regions (
                    answer_id, region_order, page_index, x0, y0, x1, y1,
                    render_dpi, join_gap_px, post_left, post_top, post_right, post_bottom
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (answer_id, *values),
            )
    summary.source_databases += 1


def _build_paper_index(paper_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    duplicates: set[str] = set()
    for path in paper_root.rglob("*.pdf"):
        if not path.is_file():
            continue
        key = path.stem.casefold()
        if key in index:
            duplicates.add(key)
        else:
            index[key] = path.resolve()
        if key.startswith("tmua_") and key.endswith("_worked_answers"):
            alias = f"{key[:-len('_worked_answers')]}_ms"
            if alias in index and index[alias] != path.resolve():
                duplicates.add(alias)
            else:
                index[alias] = path.resolve()
    if duplicates:
        preview = ", ".join(sorted(duplicates)[:5])
        raise ValueError(f"duplicate PDF stems under paper root: {preview}")
    return index


def _resolve_image_path(image_root: Path, storage_key: str) -> Path:
    relative = Path(storage_key)
    if not storage_key or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"invalid question image storage key: {storage_key}")
    path = (image_root / relative).resolve()
    if not path.is_relative_to(image_root) or not path.is_file():
        raise ValueError(f"question image does not exist: {storage_key}")
    return path


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _upsert_program(
    conn: sqlite3.Connection,
    exam_board: str,
    qualification: str,
    course_code: str,
    display_name: str,
) -> int:
    board_id = _upsert_lookup(conn, "exam_boards", exam_board, exam_board.upper())
    qualification_id = _upsert_lookup(conn, "qualifications", qualification, qualification.replace("_", " ").title())
    conn.execute(
        """
        INSERT INTO exam_programs (exam_board_id, qualification_id, code, name)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(exam_board_id, qualification_id, code) DO UPDATE SET name = excluded.name
        """,
        (board_id, qualification_id, course_code, display_name),
    )
    row = conn.execute(
        "SELECT id FROM exam_programs WHERE exam_board_id = ? AND qualification_id = ? AND code = ?",
        (board_id, qualification_id, course_code),
    ).fetchone()
    return int(row[0])


def _upsert_lookup(conn: sqlite3.Connection, table: str, code: str, name: str) -> int:
    conn.execute(
        f"INSERT INTO {table} (code, name) VALUES (?, ?) ON CONFLICT(code) DO UPDATE SET name = excluded.name",
        (code, name),
    )
    row = conn.execute(f"SELECT id FROM {table} WHERE code = ?", (code,)).fetchone()
    return int(row[0])


def _insert_paper(
    conn: sqlite3.Connection,
    program_id: int,
    qualification: str,
    exam_board: str,
    course_code: str,
    source_key: str,
) -> int:
    stable_key = f"{qualification}:{exam_board}:{course_code}:{source_key}"
    year, session, component, variant = _parse_paper_key(source_key, course_code)
    cursor = conn.execute(
        """
        INSERT INTO papers (
            exam_program_id, stable_key, source_key, year, session, component, variant
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (program_id, stable_key, source_key, year, session, component, variant),
    )
    return int(cursor.lastrowid)


def _insert_document(
    conn: sqlite3.Connection,
    paper_id: int,
    role: str,
    path: Path,
    paper_root: Path,
) -> int:
    storage_key = path.relative_to(paper_root).as_posix()
    cursor = conn.execute(
        """
        INSERT INTO paper_documents (
            paper_id, role, storage_key, original_filename, size_bytes
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (paper_id, role, storage_key, path.name, path.stat().st_size),
    )
    return int(cursor.lastrowid)


def _parse_paper_key(source_key: str, course_code: str) -> tuple[int | None, str | None, str | None, str | None]:
    cie_match = re.fullmatch(rf"{re.escape(course_code)}_([msw])(\d{{2}})_qp_(.+)", source_key, re.IGNORECASE)
    if cie_match:
        session_code, short_year, component = cie_match.groups()
        year = 2000 + int(short_year)
        variant = component[-1] if len(component) > 1 else None
        return year, f"{session_code.lower()}{short_year}", component, variant
    admissions_match = re.fullmatch(
        rf"{re.escape(course_code)}_(\d{{4}}|early_specimen)_([^_]+)_qp", source_key, re.IGNORECASE
    )
    if admissions_match:
        period, component = admissions_match.groups()
        year = int(period) if period.isdigit() else None
        return year, period, component, None
    return None, None, None, None


def _answer_role(exam_board: str, course_code: str, source_stem: str = "") -> str:
    if exam_board == "cie":
        return "mark_scheme"
    if source_stem.endswith("_worked_answers"):
        return "worked_answer"
    if course_code in {"engaa", "nsaa", "tmua"}:
        return "answer_key"
    return "worked_answer"


def _answer_kind(
    exam_board: str,
    course_code: str,
    document_id: int | None = None,
    connection: sqlite3.Connection | None = None,
) -> str:
    role = _answer_role(exam_board, course_code)
    if document_id is not None and connection is not None:
        row = connection.execute("SELECT role FROM paper_documents WHERE id = ?", (document_id,)).fetchone()
        if row is not None:
            role = str(row[0])
    return {"mark_scheme": "mark_scheme", "answer_key": "answer_key", "worked_answer": "worked_solution"}[role]


def _region_values(row: sqlite3.Row) -> tuple[object, ...]:
    return tuple(
        row[name]
        for name in (
            "region_order",
            "page_index",
            "x0",
            "y0",
            "x1",
            "y1",
            "render_dpi",
            "join_gap_px",
            "post_left",
            "post_top",
            "post_right",
            "post_bottom",
        )
    )


def _fill_summary_counts(conn: sqlite3.Connection, summary: GlobalMigrationSummary) -> None:
    for field, table in (
        ("exam_programs", "exam_programs"),
        ("papers", "papers"),
        ("paper_documents", "paper_documents"),
        ("questions", "questions"),
        ("question_texts", "question_texts"),
        ("question_regions", "question_regions"),
        ("question_images", "question_images"),
        ("answers", "answers"),
        ("answer_regions", "answer_regions"),
    ):
        setattr(summary, field, int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]))
