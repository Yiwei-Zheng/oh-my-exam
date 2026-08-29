from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.models import PaperAsset, QuestionSlice


SCHEMA_VERSION = 2


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


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exam_boards (
            id INTEGER PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY,
            exam_board_id INTEGER NOT NULL REFERENCES exam_boards(id),
            qualification TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE (exam_board_id, qualification, code)
        );

        CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY,
            subject_id INTEGER NOT NULL REFERENCES subjects(id),
            session TEXT NOT NULL,
            component TEXT NOT NULL,
            UNIQUE (subject_id, session, component)
        );

        CREATE TABLE IF NOT EXISTS paper_assets (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL REFERENCES papers(id),
            document_type TEXT NOT NULL,
            pdf_path TEXT NOT NULL,
            UNIQUE (paper_id, document_type)
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY,
            paper_id INTEGER NOT NULL REFERENCES papers(id),
            question_number TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            question_pdf_path TEXT,
            page_start INTEGER,
            page_end INTEGER,
            UNIQUE (paper_id, question_number)
        );

        CREATE TABLE IF NOT EXISTS mark_schemes (
            id INTEGER PRIMARY KEY,
            question_id INTEGER NOT NULL UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
            mark_scheme_pdf_path TEXT,
            structured_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS marking_points (
            id INTEGER PRIMARY KEY,
            mark_scheme_id INTEGER NOT NULL REFERENCES mark_schemes(id) ON DELETE CASCADE,
            mark_type TEXT NOT NULL,
            marker TEXT NOT NULL,
            text TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY,
            subject_id INTEGER NOT NULL REFERENCES subjects(id),
            name TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            UNIQUE (subject_id, name)
        );

        CREATE TABLE IF NOT EXISTS question_tags (
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (question_id, tag_id)
        );

        CREATE INDEX IF NOT EXISTS idx_questions_lookup ON questions(paper_id, question_number);
        CREATE INDEX IF NOT EXISTS idx_papers_lookup ON papers(session, component);
        """
    )
    _ensure_column(conn, "questions", "content", "TEXT NOT NULL DEFAULT ''")
    conn.execute("INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


def upsert_asset(conn: sqlite3.Connection, asset: PaperAsset, pdf_path: Path) -> int:
    board_id = _upsert(conn, "exam_boards", {"code": asset.exam_board, "name": asset.exam_board.upper()}, ["code"])
    subject_id = _upsert(
        conn,
        "subjects",
        {
            "exam_board_id": board_id,
            "qualification": asset.qualification,
            "code": asset.subject_code,
            "name": asset.subject_name,
        },
        ["exam_board_id", "qualification", "code"],
    )
    paper_id = _upsert(
        conn,
        "papers",
        {"subject_id": subject_id, "session": asset.session, "component": asset.component},
        ["subject_id", "session", "component"],
    )
    _upsert(
        conn,
        "paper_assets",
        {"paper_id": paper_id, "document_type": asset.document_type, "pdf_path": str(pdf_path)},
        ["paper_id", "document_type"],
    )
    conn.commit()
    return paper_id


def upsert_question_slice(conn: sqlite3.Connection, paper_id: int, question: QuestionSlice) -> int:
    return _upsert(
        conn,
        "questions",
        {
            "paper_id": paper_id,
            "question_number": question.question_number,
            "content": question.content,
            "question_pdf_path": str(question.pdf_path),
            "page_start": question.page_start,
            "page_end": question.page_end,
        },
        ["paper_id", "question_number"],
    )


def upsert_mark_scheme_slice(conn: sqlite3.Connection, question_id: int, mark_scheme: QuestionSlice) -> None:
    structured = {"points": list(mark_scheme.mark_scheme_points)}
    mark_scheme_id = _upsert(
        conn,
        "mark_schemes",
        {
            "question_id": question_id,
            "mark_scheme_pdf_path": str(mark_scheme.pdf_path),
            "structured_json": json.dumps(structured, ensure_ascii=False),
        },
        ["question_id"],
    )
    conn.execute("DELETE FROM marking_points WHERE mark_scheme_id = ?", (mark_scheme_id,))
    for point in mark_scheme.mark_scheme_points:
        conn.execute(
            """
            INSERT INTO marking_points (mark_scheme_id, mark_type, marker, text)
            VALUES (?, ?, ?, ?)
            """,
            (
                mark_scheme_id,
                str(point.get("type", "")),
                _format_marker(point),
                str(point.get("marking_point", "")),
            ),
        )
    conn.commit()


def _format_marker(point: dict[str, object]) -> str:
    mark_type = str(point.get("type", ""))
    score = point.get("score")
    return f"{mark_type}{score}" if score not in (None, "") else mark_type


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _upsert(conn: sqlite3.Connection, table: str, values: dict[str, object], key_columns: list[str]) -> int:
    columns = list(values)
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{column} = excluded.{column}" for column in columns if column not in key_columns)
    if updates:
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(key_columns)}) DO UPDATE SET {updates}"
        )
    else:
        sql = (
            f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) "
            f"VALUES ({placeholders})"
        )
    conn.execute(sql, tuple(values[column] for column in columns))

    where_clause = " AND ".join(f"{column} = ?" for column in key_columns)
    row = conn.execute(
        f"SELECT id FROM {table} WHERE {where_clause}",
        tuple(values[column] for column in key_columns),
    ).fetchone()
    if row is None:
        raise RuntimeError(f"failed to upsert {table}")
    return int(row[0])

