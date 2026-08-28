from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class ExamDatabase:
    id: str
    qualification: str
    exam_board: str
    course_code: str
    display_name: str
    path: Path


class CatalogNotFoundError(LookupError):
    pass


class SubjectCatalog:
    """Read-only adapter over the existing portable subject databases."""

    def __init__(self, database_root: Path) -> None:
        self.database_root = database_root.resolve()

    def list_exams(self) -> list[dict[str, object]]:
        exams = []
        for database in self._scan():
            with self._connect(database) as connection:
                paper_count = connection.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
                question_count = connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            exams.append(
                {
                    "id": database.id,
                    "qualification": database.qualification,
                    "exam_board": database.exam_board,
                    "course_code": database.course_code,
                    "display_name": database.display_name,
                    "paper_count": paper_count,
                    "question_count": question_count,
                }
            )
        return exams

    def list_questions(self, exam_id: str, query: str = "", limit: int = 50) -> list[dict[str, object]]:
        database = self.get_exam(exam_id)
        sql = """
            SELECT q.id, q.question_number, q.local_question_key,
                   p.id AS paper_id, p.qp_stem, t.content
            FROM questions q
            JOIN papers p ON p.id = q.paper_id
            LEFT JOIN question_texts t ON t.question_id = q.id
        """
        parameters: list[object] = []
        if query.strip():
            sql += " WHERE lower(COALESCE(t.content, '')) LIKE ?"
            parameters.append(f"%{query.strip().lower()}%")
        sql += " ORDER BY p.qp_stem, q.id LIMIT ?"
        parameters.append(limit)
        with self._connect(database) as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._question_summary(row) for row in rows]

    def get_question(self, exam_id: str, question_id: int) -> dict[str, object]:
        database = self.get_exam(exam_id)
        with self._connect(database) as connection:
            question = connection.execute(
                """
                SELECT q.id, q.question_number, q.local_question_key,
                       p.id AS paper_id, p.qp_stem, p.ms_stem, t.content
                FROM questions q
                JOIN papers p ON p.id = q.paper_id
                LEFT JOIN question_texts t ON t.question_id = q.id
                WHERE q.id = ?
                """,
                (question_id,),
            ).fetchone()
            if question is None:
                raise CatalogNotFoundError(f"question not found: {question_id}")
            crop_rows = connection.execute(
                """
                SELECT source_type, region_order, page_index, x0, y0, x1, y1,
                       render_dpi, join_gap_px, post_left, post_top, post_right, post_bottom
                FROM crop_regions
                WHERE question_id = ?
                ORDER BY source_type, region_order
                """,
                (question_id,),
            ).fetchall()
        result = self._question_summary(question)
        result.update(
            {
                "answer_stem": question["ms_stem"],
                "crop_regions": [dict(row) for row in crop_rows],
            }
        )
        return result

    def get_paper_stem(self, exam_id: str, paper_id: int, kind: str) -> str:
        if kind not in {"question", "answer"}:
            raise CatalogNotFoundError(f"unsupported paper kind: {kind}")
        database = self.get_exam(exam_id)
        column = "qp_stem" if kind == "question" else "ms_stem"
        with self._connect(database) as connection:
            row = connection.execute(f"SELECT {column} FROM papers WHERE id = ?", (paper_id,)).fetchone()
        if row is None or not row[0]:
            raise CatalogNotFoundError(f"paper not found: {paper_id}")
        return str(row[0])

    def get_exam(self, exam_id: str) -> ExamDatabase:
        for database in self._scan():
            if database.id == exam_id:
                return database
        raise CatalogNotFoundError(f"exam not found: {exam_id}")

    def _scan(self) -> list[ExamDatabase]:
        if not self.database_root.is_dir():
            return []
        databases = []
        for path in sorted(self.database_root.rglob("*.sqlite")):
            uri = f"{path.resolve().as_uri()}?mode=ro"
            try:
                with sqlite3.connect(uri, uri=True) as connection:
                    row = connection.execute(
                        "SELECT qualification, exam_board, course_code, course_display_name "
                        "FROM database_info LIMIT 1"
                    ).fetchone()
            except sqlite3.Error:
                continue
            if row is None or not all(isinstance(value, str) and value.strip() for value in row[:3]):
                continue
            qualification, exam_board, course_code, display_name = (str(value).strip() for value in row)
            if qualification != "admissions":
                continue
            databases.append(
                ExamDatabase(
                    id=f"{qualification}:{exam_board}:{course_code}",
                    qualification=qualification,
                    exam_board=exam_board,
                    course_code=course_code,
                    display_name=display_name or course_code.upper(),
                    path=path.resolve(),
                )
            )
        return databases

    @staticmethod
    def _connect(database: ExamDatabase) -> sqlite3.Connection:
        uri = f"{database.path.as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _question_summary(row: sqlite3.Row) -> dict[str, object]:
        return {
            "id": row["id"],
            "paper_id": row["paper_id"],
            "paper_stem": row["qp_stem"],
            "local_key": row["local_question_key"],
            "question_number": row["question_number"],
            "content": row["content"] or "",
        }
