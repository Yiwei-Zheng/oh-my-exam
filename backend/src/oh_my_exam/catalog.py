from __future__ import annotations

from contextlib import closing
from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path
import re
import sqlite3


_SEARCH_TERM = re.compile(r"[a-z0-9]+")


def _term_counts(content: str) -> Counter[str]:
    return Counter(_SEARCH_TERM.findall(content.casefold()))


def _cosine_similarity(source: Counter[str], target: Counter[str]) -> float:
    if not source or not target:
        return 0.0
    dot_product = sum(count * target.get(term, 0) for term, count in source.items())
    if not dot_product:
        return 0.0
    source_norm = math.sqrt(sum(count * count for count in source.values()))
    target_norm = math.sqrt(sum(count * count for count in target.values()))
    return dot_product / (source_norm * target_norm)


class CatalogNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class QuestionImage:
    storage_key: str
    filename: str


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

    def asset_inventory(self) -> dict[str, object]:
        """Return publication counts and coverage without exposing storage paths."""
        with closing(self._connect()) as connection:
            counts = {
                key: self._count_table(connection, table)
                for key, table in (
                    ("exam_programs", "exam_programs"),
                    ("papers", "papers"),
                    ("questions", "questions"),
                    ("source_documents", "paper_documents"),
                )
            }
            searchable = int(connection.execute(
                """
                SELECT COUNT(DISTINCT question_id) FROM question_texts
                WHERE text_kind = 'search' AND trim(content) != ''
                """
            ).fetchone()[0]) if self._table_exists(connection, "question_texts") else 0
            answered = int(connection.execute(
                "SELECT COUNT(DISTINCT question_id) FROM answers"
            ).fetchone()[0]) if self._table_exists(connection, "answers") else 0
        question_total = counts["questions"]
        return counts | {
            "searchable_questions": searchable,
            "answered_questions": answered,
            "searchable_coverage": searchable / question_total if question_total else 0.0,
            "answer_coverage": answered / question_total if question_total else 0.0,
            "by_exam": self.list_exams(),
        }

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
                f"program:{qualification}:{board}:{program}", program.upper(), "program"
            ) | {"paper_count": 0, "question_count": 0})
            if program_node not in board_node["children"]:
                board_node["children"].append(program_node)
            if row["paper_id"] is not None:
                program_node["paper_count"] = int(program_node["paper_count"]) + 1
                program_node["question_count"] = (
                    int(program_node["question_count"]) + int(row["question_count"])
                )
                year = str(row["year"] or "Unknown year")
                year_node = years.setdefault(
                    (qualification, board, program, year),
                    self._tree_node(f"year:{qualification}:{board}:{program}:{year}", year, "year"),
                )
                if year_node not in program_node["children"]:
                    program_node["children"].append(year_node)
                session = str(row["session"] or "Unspecified")
                paper_parent = year_node
                if session.casefold() != year.casefold():
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
                    paper_parent = session_node
                label = f"{row['year']} · {row['source_key']}" if row["year"] else str(row["source_key"])
                paper_parent["children"].append({
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

    def search_questions(
        self,
        query: str = "",
        *,
        exam_id: str | None = None,
        topic_codes: tuple[str, ...] = (),
        limit: int = 50,
        match_all_terms: bool = True,
        similarity_text: str | None = None,
    ) -> list[dict[str, object]]:
        """Search identity, extracted text, and managed syllabus topics."""
        normalized_query = query.strip().casefold()
        tokens = tuple(dict.fromkeys(part for part in normalized_query.split() if part))
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id) if exam_id else None
            has_features = self._table_exists(connection, "question_features")
            select_topics = (
                "GROUP_CONCAT(DISTINCT fl.name) AS topics"
                if has_features else "'' AS topics"
            )
            joins = ""
            if has_features:
                joins = """
                    LEFT JOIN question_features qf ON qf.question_id = qu.id
                    LEFT JOIN features f ON f.id = qf.feature_id
                    LEFT JOIN feature_labels fl ON fl.feature_id = f.id AND fl.language = 'en'
                """
            sql = f"""
                SELECT qu.id, qu.stable_key, qu.question_number, qu.local_key,
                       p.id AS paper_id, p.source_key AS paper_key, qt.content,
                       ql.code AS qualification, eb.code AS exam_board, ep.code AS course_code,
                       {select_topics}
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                JOIN exam_programs ep ON ep.id = p.exam_program_id
                JOIN qualifications ql ON ql.id = ep.qualification_id
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                LEFT JOIN question_texts qt
                  ON qt.question_id = qu.id AND qt.text_kind = 'search' AND qt.language = 'en'
                {joins}
                WHERE 1 = 1
            """
            parameters: list[object] = []
            if program_id is not None:
                sql += " AND p.exam_program_id = ?"
                parameters.append(program_id)
            if tokens:
                clauses: list[str] = []
                for token in tokens:
                    clauses.append("(lower(COALESCE(qt.content, '')) LIKE ? OR lower(qu.stable_key) LIKE ?)")
                    parameters.extend((f"%{token}%", f"%{token}%"))
                operator = " AND " if match_all_terms else " OR "
                sql += " AND (" + operator.join(clauses) + ")"
            if topic_codes and has_features:
                placeholders = ", ".join("?" for _ in topic_codes)
                sql += f"""
                    AND EXISTS (
                        SELECT 1
                        FROM question_features filter_qf
                        JOIN features filter_f ON filter_f.id = filter_qf.feature_id
                        WHERE filter_qf.question_id = qu.id
                          AND filter_f.canonical_code IN ({placeholders})
                    )
                """
                parameters.extend(topic_codes)
            sql += " GROUP BY qu.id ORDER BY p.year DESC, p.source_key, qu.sort_order"
            if similarity_text is None:
                sql += " LIMIT ?"
                parameters.append(max(limit * 5, limit))
            rows = connection.execute(sql, parameters).fetchall()

        results: list[dict[str, object]] = []
        similarity_terms = _term_counts(similarity_text or "")
        for row in rows:
            content = str(row["content"] or "")
            haystack = f"{row['stable_key']} {content}".casefold()
            if similarity_text is not None:
                score: float | int = _cosine_similarity(
                    similarity_terms,
                    _term_counts(content),
                )
            else:
                lexical_hits = sum(haystack.count(token) for token in tokens)
                phrase_bonus = 2 if normalized_query and normalized_query in haystack else 0
                score = lexical_hits + phrase_bonus
            summary = self._question_summary(row)
            summary.update({
                "exam_id": f"{row['qualification']}:{row['exam_board']}:{row['course_code']}",
                "score": score,
            })
            results.append(summary)
        results.sort(key=lambda item: (-float(item["score"]), str(item["stable_key"])))
        return results[:limit]

    def list_topics(self, exam_id: str | None = None) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            if not self._table_exists(connection, "syllabus_topics"):
                return []
            sql = """
                SELECT st.id, st.parent_topic_id, f.canonical_code AS code,
                       st.title, st.description,
                       ql.code AS qualification, eb.code AS exam_board, ep.code AS course_code,
                       COUNT(DISTINCT qf.question_id) AS question_count
                FROM syllabus_topics st
                JOIN syllabuses s ON s.id = st.syllabus_id
                JOIN exam_programs ep ON ep.id = s.exam_program_id
                JOIN qualifications ql ON ql.id = ep.qualification_id
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                JOIN syllabus_topic_features stf ON stf.syllabus_topic_id = st.id
                JOIN features f ON f.id = stf.feature_id
                LEFT JOIN question_features qf ON qf.feature_id = f.id
                WHERE 1 = 1
            """
            parameters: list[object] = []
            if exam_id:
                sql += " AND ep.id = ?"
                parameters.append(self._program_id(connection, exam_id))
            sql += " GROUP BY st.id ORDER BY ep.code, st.code"
            rows = connection.execute(sql, parameters).fetchall()
        return [
            {
                "id": row["id"], "parent_id": row["parent_topic_id"],
                "code": row["code"], "title": row["title"], "description": row["description"],
                "exam_id": f"{row['qualification']}:{row['exam_board']}:{row['course_code']}",
                "question_count": row["question_count"],
            }
            for row in rows
        ]

    def list_similar_questions(
        self,
        exam_id: str,
        question_id: int,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            exists = connection.execute(
                """
                SELECT 1 FROM questions q JOIN papers p ON p.id = q.paper_id
                WHERE q.id = ? AND p.exam_program_id = ?
                """,
                (question_id, program_id),
            ).fetchone()
            if exists is None:
                raise CatalogNotFoundError(f"question not found: {question_id}")
            if not self._table_exists(connection, "question_similarities"):
                return []
            rows = connection.execute(
                """
                SELECT target.id, target.stable_key, target.question_number, target.local_key,
                       p.id AS paper_id, p.source_key AS paper_key, qt.content,
                       ql.code AS qualification, eb.code AS exam_board, ep.code AS course_code,
                       qs.rank, qs.score,
                       GROUP_CONCAT(DISTINCT target_labels.name) AS topics,
                       GROUP_CONCAT(DISTINCT shared_labels.name) AS shared_topics
                FROM question_similarities qs
                JOIN similarity_algorithms sa ON sa.id = qs.algorithm_id
                JOIN questions target ON target.id = qs.target_question_id
                JOIN papers p ON p.id = target.paper_id
                JOIN exam_programs ep ON ep.id = p.exam_program_id
                JOIN qualifications ql ON ql.id = ep.qualification_id
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                LEFT JOIN question_texts qt
                  ON qt.question_id = target.id AND qt.text_kind = 'search' AND qt.language = 'en'
                LEFT JOIN question_features source_features
                  ON source_features.question_id = qs.source_question_id
                LEFT JOIN question_features target_features
                  ON target_features.question_id = target.id
                 AND target_features.feature_id = source_features.feature_id
                LEFT JOIN feature_labels shared_labels
                  ON shared_labels.feature_id = target_features.feature_id AND shared_labels.language = 'en'
                LEFT JOIN question_features target_all_features
                  ON target_all_features.question_id = target.id
                LEFT JOIN feature_labels target_labels
                  ON target_labels.feature_id = target_all_features.feature_id AND target_labels.language = 'en'
                WHERE qs.source_question_id = ? AND sa.name = 'syllabus_tfidf'
                GROUP BY target.id, qs.rank, qs.score
                ORDER BY qs.rank
                LIMIT ?
                """,
                (question_id, limit),
            ).fetchall()
        return [
            self._question_summary(row) | {
                "rank": row["rank"],
                "score": row["score"],
                "shared_topics": [item for item in str(row["shared_topics"] or "").split(",") if item],
            }
            for row in rows
        ]

    def get_question(self, exam_id: str, question_id: int) -> dict[str, object]:
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            question = connection.execute(
                """
                SELECT qu.id, qu.stable_key, qu.question_number, qu.local_key,
                       p.id AS paper_id, p.source_key AS paper_key, qt.content,
                       ql.code AS qualification, eb.code AS exam_board, ep.code AS course_code,
                       GROUP_CONCAT(DISTINCT fl.name) AS topics
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                JOIN exam_programs ep ON ep.id = p.exam_program_id
                JOIN qualifications ql ON ql.id = ep.qualification_id
                JOIN exam_boards eb ON eb.id = ep.exam_board_id
                LEFT JOIN question_texts qt
                  ON qt.question_id = qu.id AND qt.text_kind = 'search' AND qt.language = 'en'
                LEFT JOIN question_features qf ON qf.question_id = qu.id
                LEFT JOIN feature_labels fl ON fl.feature_id = qf.feature_id AND fl.language = 'en'
                WHERE qu.id = ? AND p.exam_program_id = ?
                GROUP BY qu.id
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

    def get_question_image(self, exam_id: str, question_id: int, kind: str) -> QuestionImage:
        if kind not in {"question", "answer"}:
            raise CatalogNotFoundError(f"unsupported question image kind: {kind}")
        with closing(self._connect()) as connection:
            program_id = self._program_id(connection, exam_id)
            if not self._table_exists(connection, "question_images"):
                raise CatalogNotFoundError("catalog has no pre-rendered question images")
            image = connection.execute(
                """
                SELECT qi.storage_key, qi.original_filename
                FROM question_images qi
                JOIN questions qu ON qu.id = qi.question_id
                JOIN papers p ON p.id = qu.paper_id
                WHERE qu.id = ? AND p.exam_program_id = ? AND qi.image_kind = ?
                LIMIT 1
                """,
                (question_id, program_id, kind),
            ).fetchone()
            question_exists = connection.execute(
                """
                SELECT 1
                FROM questions qu
                JOIN papers p ON p.id = qu.paper_id
                WHERE qu.id = ? AND p.exam_program_id = ?
                """,
                (question_id, program_id),
            ).fetchone()
        if question_exists is None:
            raise CatalogNotFoundError(f"question not found: {question_id}")
        if image is None:
            raise CatalogNotFoundError(f"pre-rendered question image not found: {question_id}/{kind}")
        return QuestionImage(
            storage_key=str(image["storage_key"]),
            filename=str(image["original_filename"]),
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
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        return connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
            (table,),
        ).fetchone() is not None

    @classmethod
    def _count_table(cls, connection: sqlite3.Connection, table: str) -> int:
        if not cls._table_exists(connection, table):
            return 0
        return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])

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
        result: dict[str, object] = {
            "id": row["id"],
            "stable_key": row["stable_key"],
            "paper_id": row["paper_id"],
            "paper_key": row["paper_key"],
            "local_key": row["local_key"],
            "question_number": row["question_number"],
            "content": row["content"] or "",
        }
        keys = set(row.keys())
        if {"qualification", "exam_board", "course_code"} <= keys:
            result["exam_id"] = f"{row['qualification']}:{row['exam_board']}:{row['course_code']}"
        if "topics" in keys:
            topics = [item for item in str(row["topics"] or "").split(",") if item]
            if not topics and "course_code" in keys:
                topics = [str(row["course_code"]).upper()]
            result["topics"] = topics
        return result
