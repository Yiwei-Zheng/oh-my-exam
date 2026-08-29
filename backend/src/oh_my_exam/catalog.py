from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3


class CatalogNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class QuestionDocument:
    storage_key: str
    filename: str
    crop_regions: tuple[dict[str, object], ...]


class GlobalCatalog:
    """Read-only adapter over the normalized global question catalog."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()

    def list_exams(self) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT ep.id, ep.code, ep.name,
                       eb.code AS exam_board, ql.code AS qualification,
                       COUNT(DISTINCT p.id) AS paper_count,
                       COUNT(DISTINCT qu.id) AS question_count
                FROM exam_programs ep
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                JOIN qualifications ql ON ql.id = ep.qualification_id
                LEFT JOIN papers p ON p.exam_program_id = ep.id
                LEFT JOIN questions qu ON qu.paper_id = p.id
                GROUP BY ep.id
                ORDER BY ql.code, eb.code, ep.code
                """
            ).fetchall()
        return [
            {
                "id": self._exam_id(row),
                "qualification": row["qualification"],
                "exam_board": row["exam_board"],
                "course_code": row["code"],
                "display_name": row["name"],
                "paper_count": row["paper_count"],
                "question_count": row["question_count"],
            }
            for row in rows
        ]

    def question_tree(self) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT ql.code AS qualification, ql.name AS qualification_name,
                       eb.code AS board, eb.name AS board_name,
                       ep.code AS program, ep.name AS program_name,
                       p.id AS paper_id, p.source_key, p.year, p.session,
                       COUNT(qu.id) AS question_count
                FROM qualifications ql
                JOIN exam_programs ep ON ep.qualification_id = ql.id
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                LEFT JOIN papers p ON p.exam_program_id = ep.id
                LEFT JOIN questions qu ON qu.paper_id = p.id
                GROUP BY ql.id, eb.id, ep.id, p.id
                ORDER BY ql.code, eb.code, ep.code, p.year DESC, p.source_key
                """
            ).fetchall()
        roots: dict[str, dict[str, object]] = {}
        boards: dict[tuple[str, str], dict[str, object]] = {}
        programs: dict[tuple[str, str, str], dict[str, object]] = {}
        years: dict[tuple[str, str, str, str], dict[str, object]] = {}
        sessions: dict[tuple[str, str, str, str, str], dict[str, object]] = {}
        for row in rows:
            qualification = str(row["qualification"])
            board = str(row["board"])
            program = str(row["program"])
            root = roots.setdefault(qualification, self._tree_node(
                f"qualification:{qualification}", str(row["qualification_name"]), "qualification"
            ))
            board_node = boards.setdefault((qualification, board), self._tree_node(
                f"board:{qualification}:{board}", str(row["board_name"]), "board"
            ))
            if board_node not in root["children"]:
                root["children"].append(board_node)
            program_node = programs.setdefault((qualification, board, program), self._tree_node(
                f"program:{qualification}:{board}:{program}", str(row["program_name"]), "program"
            ))
            if program_node not in board_node["children"]:
                board_node["children"].append(program_node)
            if row["paper_id"] is not None:
                year = str(row["year"] or "Unknown year")
                year_node = years.setdefault(
                    (qualification, board, program, year),
                    self._tree_node(f"year:{qualification}:{board}:{program}:{year}", year, "year"),
                )
                if year_node not in program_node["children"]:
                    program_node["children"].append(year_node)
                session = str(row["session"] or "Unspecified")
                session_node = sessions.setdefault(
                    (qualification, board, program, year, session),
                    self._tree_node(
                        f"session:{qualification}:{board}:{program}:{year}:{session}",
                        session.upper(),
                        "session",
                    ),
                )
                if session_node not in year_node["children"]:
                    year_node["children"].append(session_node)
                label = f"{row['year']} · {row['source_key']}" if row["year"] else str(row["source_key"])
                session_node["children"].append({
                    "id": f"paper:{row['paper_id']}", "label": label, "kind": "paper",
                    "count": int(row["question_count"]), "children": [],
                    "paper_id": int(row["paper_id"]),
                    "exam_id": f"{qualification}:{board}:{program}",
                    "year": row["year"], "session": row["session"] or "",
                })
        return list(roots.values())

    def list_paper_questions(self, paper_id: int) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT qu.id, qu.stable_key, qu.question_number, qu.local_key,
                       p.id AS paper_id, p.source_key AS paper_key, qt.content,
                       ql.code AS qualification, eb.code AS exam_board, ep.code AS course_code
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                JOIN exam_programs ep ON ep.id = p.exam_program_id
                JOIN qualifications ql ON ql.id = ep.qualification_id
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                LEFT JOIN question_texts qt
                  ON qt.question_id = qu.id AND qt.text_kind = 'search' AND qt.language = 'en'
                WHERE p.id = ?
                ORDER BY qu.sort_order, qu.id
                """,
                (paper_id,),
            ).fetchall()
        if not rows:
            raise CatalogNotFoundError(f"paper not found or empty: {paper_id}")
        return [
            self._question_summary(row)
            | {"exam_id": f"{row['qualification']}:{row['exam_board']}:{row['course_code']}"}
            for row in rows
        ]

    def list_questions(self, exam_id: str, query: str = "", limit: int = 50) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            sql = """
                SELECT qu.id, qu.stable_key, qu.question_number, qu.local_key,
                       p.id AS paper_id, p.source_key AS paper_key, qt.content
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                LEFT JOIN question_texts qt
                  ON qt.question_id = qu.id AND qt.text_kind = 'search' AND qt.language = 'en'
                WHERE p.exam_program_id = ?
            """
            parameters: list[object] = [program_id]
            if query.strip():
                sql += " AND lower(COALESCE(qt.content, '')) LIKE ?"
                parameters.append(f"%{query.strip().lower()}%")
            sql += " ORDER BY p.year, p.source_key, qu.sort_order LIMIT ?"
            parameters.append(limit)
            rows = connection.execute(sql, parameters).fetchall()
        return [self._question_summary(row) for row in rows]

    def get_question(self, exam_id: str, question_id: int) -> dict[str, object]:
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            question = connection.execute(
                """
                SELECT qu.id, qu.stable_key, qu.question_number, qu.local_key,
                       p.id AS paper_id, p.source_key AS paper_key, qt.content
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                LEFT JOIN question_texts qt
                  ON qt.question_id = qu.id AND qt.text_kind = 'search' AND qt.language = 'en'
                WHERE qu.id = ? AND p.exam_program_id = ?
                """,
                (question_id, program_id),
            ).fetchone()
            if question is None:
                raise CatalogNotFoundError(f"question not found: {question_id}")
            crop_rows = connection.execute(
                """
                SELECT 0 AS source_type, qr.region_order, qr.page_index,
                       qr.x0, qr.y0, qr.x1, qr.y1, qr.render_dpi, qr.join_gap_px,
                       qr.post_left, qr.post_top, qr.post_right, qr.post_bottom
                FROM question_regions qr
                WHERE qr.question_id = ?
                UNION ALL
                SELECT 1 AS source_type, ar.region_order, ar.page_index,
                       ar.x0, ar.y0, ar.x1, ar.y1, ar.render_dpi, ar.join_gap_px,
                       ar.post_left, ar.post_top, ar.post_right, ar.post_bottom
                FROM answers a
                JOIN answer_regions ar ON ar.answer_id = a.id
                WHERE a.question_id = ?
                ORDER BY source_type, region_order
                """,
                (question_id, question_id),
            ).fetchall()
            answer_version = connection.execute(
                """
                SELECT av.version, av.raw_text, av.markdown, av.status
                FROM answers a
                JOIN answer_versions av ON av.answer_id = a.id
                WHERE a.question_id = ?
                ORDER BY av.version DESC, av.id DESC
                LIMIT 1
                """,
                (question_id,),
            ).fetchone()
        result = self._question_summary(question)
        result["crop_regions"] = [dict(row) for row in crop_rows]
        result["answer_structured"] = dict(answer_version) if answer_version else None
        return result

    def save_answer_revision(self, question_id: int, raw_text: str, markdown: str) -> dict[str, object]:
        with closing(self._connect_writable()) as connection:
            answer = connection.execute(
                "SELECT id FROM answers WHERE question_id = ? ORDER BY id LIMIT 1",
                (question_id,),
            ).fetchone()
            if answer is None:
                raise CatalogNotFoundError(f"answer not found for question: {question_id}")
            version = int(connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM answer_versions WHERE answer_id = ?",
                (answer["id"],),
            ).fetchone()[0])
            cursor = connection.execute(
                """
                INSERT INTO answer_versions (answer_id, version, language, raw_text, markdown, status)
                VALUES (?, ?, 'en', ?, ?, 'published')
                """,
                (answer["id"], version, raw_text, markdown),
            )
            connection.commit()
        return {
            "id": cursor.lastrowid,
            "version": version,
            "raw_text": raw_text,
            "markdown": markdown,
            "status": "published",
        }

    def get_question_document(self, exam_id: str, question_id: int, kind: str) -> QuestionDocument:
        if kind not in {"question", "answer"}:
            raise CatalogNotFoundError(f"unsupported paper kind: {kind}")
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            question = connection.execute(
                """
                SELECT qu.id, qu.local_key
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                WHERE qu.id = ? AND p.exam_program_id = ?
                """,
                (question_id, program_id),
            ).fetchone()
            if question is None:
                raise CatalogNotFoundError(f"question not found: {question_id}")
            if kind == "question":
                document = connection.execute(
                    """
                    SELECT pd.storage_key, pd.original_filename
                    FROM question_regions qr
                    JOIN paper_documents pd ON pd.id = qr.document_id
                    WHERE qr.question_id = ?
                    ORDER BY qr.region_order
                    LIMIT 1
                    """,
                    (question_id,),
                ).fetchone()
                regions = connection.execute(
                    """
                    SELECT region_order, page_index, x0, y0, x1, y1, render_dpi,
                           post_left, post_top, post_right, post_bottom
                    FROM question_regions
                    WHERE question_id = ?
                    ORDER BY region_order
                    """,
                    (question_id,),
                ).fetchall()
            else:
                document = connection.execute(
                    """
                    SELECT pd.storage_key, pd.original_filename, a.id AS answer_id
                    FROM answers a
                    JOIN paper_documents pd ON pd.id = a.source_document_id
                    WHERE a.question_id = ?
                    ORDER BY CASE a.answer_kind
                        WHEN 'worked_solution' THEN 0
                        WHEN 'mark_scheme' THEN 1
                        WHEN 'answer_key' THEN 2
                        ELSE 3
                    END, a.id
                    LIMIT 1
                    """,
                    (question_id,),
                ).fetchone()
                regions = [] if document is None else connection.execute(
                    """
                    SELECT region_order, page_index, x0, y0, x1, y1, render_dpi,
                           post_left, post_top, post_right, post_bottom
                    FROM answer_regions
                    WHERE answer_id = ?
                    ORDER BY region_order
                    """,
                    (document["answer_id"],),
                ).fetchall()
        if document is None or not regions:
            raise CatalogNotFoundError(f"question document not found: {question_id}/{kind}")
        source_name = Path(str(document["original_filename"])).stem
        return QuestionDocument(
            storage_key=str(document["storage_key"]),
            filename=f"{source_name}_{question['local_key']}.pdf",
            crop_regions=tuple(dict(region) for region in regions),
        )

    def get_paper_storage_key(self, exam_id: str, paper_id: int, kind: str) -> str:
        if kind not in {"question", "answer"}:
            raise CatalogNotFoundError(f"unsupported paper kind: {kind}")
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            roles = (
                ("question_paper",)
                if kind == "question"
                else ("worked_answer", "mark_scheme", "answer_key")
            )
            placeholders = ", ".join("?" for _ in roles)
            row = connection.execute(
                f"""
                SELECT pd.storage_key
                FROM paper_documents pd
                JOIN papers p ON p.id = pd.paper_id
                WHERE p.id = ? AND p.exam_program_id = ? AND pd.role IN ({placeholders})
                ORDER BY CASE pd.role
                    WHEN 'worked_answer' THEN 0
                    WHEN 'mark_scheme' THEN 1
                    WHEN 'answer_key' THEN 2
                    ELSE 3
                END, pd.id
                LIMIT 1
                """,
                (paper_id, program_id, *roles),
            ).fetchone()
        if row is None:
            raise CatalogNotFoundError(f"paper not found: {paper_id}/{kind}")
        return str(row["storage_key"])

    def _connect(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise CatalogNotFoundError(f"global catalog not found: {self.database_path}")
        uri = f"{self.database_path.as_uri()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def _connect_writable(self) -> sqlite3.Connection:
        if not self.database_path.is_file():
            raise CatalogNotFoundError(f"global catalog not found: {self.database_path}")
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _tree_node(node_id: str, label: str, kind: str) -> dict[str, object]:
        return {"id": node_id, "label": label, "kind": kind, "children": []}

    @staticmethod
    def _program_id(connection: sqlite3.Connection, exam_id: str) -> int:
        parts = exam_id.split(":")
        if len(parts) != 3:
            raise CatalogNotFoundError(f"invalid exam id: {exam_id}")
        qualification, exam_board, course_code = parts
        row = connection.execute(
            """
            SELECT ep.id
            FROM exam_programs ep
            JOIN exam_boards eb ON eb.id = ep.exam_board_id
            JOIN qualifications ql ON ql.id = ep.qualification_id
            WHERE ql.code = ? AND eb.code = ? AND ep.code = ?
            """,
            (qualification, exam_board, course_code),
        ).fetchone()
        if row is None:
            raise CatalogNotFoundError(f"exam not found: {exam_id}")
        return int(row[0])

    @staticmethod
    def _exam_id(row: sqlite3.Row) -> str:
        return f"{row['qualification']}:{row['exam_board']}:{row['code']}"

    @staticmethod
    def _question_summary(row: sqlite3.Row) -> dict[str, object]:
        return {
            "id": row["id"],
            "stable_key": row["stable_key"],
            "paper_id": row["paper_id"],
            "paper_key": row["paper_key"],
            "local_key": row["local_key"],
            "question_number": row["question_number"],
            "content": row["content"] or "",
        }
