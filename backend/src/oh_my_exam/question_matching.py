from __future__ import annotations

from collections import Counter, defaultdict
from contextlib import closing
from dataclasses import dataclass
from itertools import chain
import json
import math
from pathlib import Path
import re
import sqlite3

from oh_my_exam.pipelines.packaging.global_schema import migrate_global_catalog


ALGORITHM_NAME = "syllabus_tfidf"
ALGORITHM_VERSION = "3"
_TOKEN = re.compile(r"[a-z][a-z0-9']{1,}|\d+(?:\.\d+)?", re.IGNORECASE)
_STOP_WORDS = {
    "and", "are", "can", "determine", "find", "for", "from", "given", "hence", "is",
    "of", "or", "show", "that", "the", "then", "this", "to", "using", "with", "write",
}


@dataclass(frozen=True)
class TopicSpec:
    qualification: str
    exam_board: str
    course_code: str
    code: str
    title: str
    description: str
    components: frozenset[str]
    terms: tuple[str, ...]
    broad: bool = False
    parent_code: str | None = None

    @property
    def canonical_code(self) -> str:
        return f"syllabus:{self.exam_board}:{self.qualification}:{self.course_code}:{self.code}"

    @property
    def program_key(self) -> tuple[str, str, str]:
        return self.qualification, self.exam_board, self.course_code


@dataclass
class MatchingSummary:
    syllabuses: int = 0
    topics: int = 0
    tagged_questions: int = 0
    question_tags: int = 0
    similarities: int = 0


def load_topic_specs(path: Path) -> list[TopicSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    specs: list[TopicSpec] = []
    for course in payload["courses"]:
        for topic in course["topics"]:
            specs.append(TopicSpec(
                qualification=str(course.get("qualification", "a_level")),
                exam_board=str(course.get("exam_board", "cie")),
                course_code=str(course["course_code"]),
                code=str(topic["code"]),
                title=str(topic["title"]),
                description=str(topic.get("description", "")),
                components=frozenset(str(item) for item in topic.get("components", [])),
                terms=tuple(str(item).casefold() for item in topic.get("terms", [])),
                broad=bool(topic.get("broad", False)),
                parent_code=str(topic["parent"]) if topic.get("parent") else None,
            ))
    return specs


def rebuild_question_matching(
    database_path: Path,
    topic_catalog_path: Path,
    *,
    top_k: int = 12,
) -> MatchingSummary:
    """Rebuild managed syllabus tags and explainable, sparse text similarities."""
    specs = load_topic_specs(topic_catalog_path)
    by_program: dict[tuple[str, str, str], list[TopicSpec]] = defaultdict(list)
    for spec in specs:
        by_program[spec.program_key].append(spec)

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row
        migrate_global_catalog(connection)
        _clear_managed_rows(connection, specs)
        feature_ids = _write_topics(connection, by_program, topic_catalog_path)
        rows = connection.execute(
            """
            SELECT q.id, q.paper_id, qt.content, p.component, ep.code AS course_code,
                   ql.code AS qualification, eb.code AS exam_board
            FROM questions q
            JOIN papers p ON p.id = q.paper_id
            JOIN exam_programs ep ON ep.id = p.exam_program_id
            JOIN qualifications ql ON ql.id = ep.qualification_id
            JOIN exam_boards eb ON eb.id = ep.exam_board_id
            LEFT JOIN question_texts qt
              ON qt.question_id = q.id AND qt.text_kind = 'search' AND qt.language = 'en'
            ORDER BY q.id
            """
        ).fetchall()
        tags = _classify_questions(rows, by_program, feature_ids)
        connection.executemany(
            """
            INSERT INTO question_features (question_id, feature_id, role, weight)
            VALUES (?, ?, ?, ?)
            """,
            [
                (question_id, feature_id, "secondary" if broad else "primary", weight)
                for question_id, values in tags.items()
                for feature_id, weight, broad in values
            ],
        )
        algorithm_id = _write_algorithm(connection, top_k)
        similarities = _build_similarities(rows, tags, top_k=top_k)
        connection.executemany(
            """
            INSERT INTO question_similarities (
                source_question_id, target_question_id, algorithm_id, rank, score
            ) VALUES (?, ?, ?, ?, ?)
            """,
            [(*pair, algorithm_id, rank, score) for pair, rank, score in similarities],
        )
        connection.commit()
        return MatchingSummary(
            syllabuses=len(by_program),
            topics=len(specs),
            tagged_questions=len(tags),
            question_tags=sum(len(values) for values in tags.values()),
            similarities=len(similarities),
        )


def _clear_managed_rows(connection: sqlite3.Connection, specs: list[TopicSpec]) -> None:
    managed_prefixes = sorted({
        f"syllabus:{spec.exam_board}:{spec.qualification}:{spec.course_code}:%"
        for spec in specs
    })
    managed_where = " OR ".join("canonical_code LIKE ?" for _ in managed_prefixes)
    if managed_prefixes:
        connection.execute(
            f"DELETE FROM question_features WHERE feature_id IN "
            f"(SELECT id FROM features WHERE {managed_where})",
            managed_prefixes,
        )
    connection.execute(
        "DELETE FROM question_similarities WHERE algorithm_id IN "
        "(SELECT id FROM similarity_algorithms WHERE name = ?)",
        (ALGORITHM_NAME,),
    )
    connection.execute("DELETE FROM similarity_algorithms WHERE name = ?", (ALGORITHM_NAME,))
    connection.execute("DELETE FROM syllabuses WHERE name LIKE 'Managed syllabus topics:%'")
    if managed_prefixes:
        connection.execute(f"DELETE FROM features WHERE {managed_where}", managed_prefixes)


def _write_topics(
    connection: sqlite3.Connection,
    by_program: dict[tuple[str, str, str], list[TopicSpec]],
    source_path: Path,
) -> dict[str, int]:
    feature_ids: dict[str, int] = {}
    for (qualification, exam_board, course_code), specs in by_program.items():
        program = connection.execute(
            """
            SELECT ep.id FROM exam_programs ep
            JOIN qualifications ql ON ql.id = ep.qualification_id
            JOIN exam_boards eb ON eb.id = ep.exam_board_id
            WHERE ql.code = ? AND eb.code = ? AND ep.code = ?
            """,
            (qualification, exam_board, course_code),
        ).fetchone()
        if program is None:
            continue
        syllabus_id = connection.execute(
            """
            INSERT INTO syllabuses (exam_program_id, name, effective_from_year, storage_key)
            VALUES (?, ?, 2026, ?)
            """,
            (program["id"], f"Managed syllabus topics:{course_code}:2026-2027", source_path.as_posix()),
        ).lastrowid
        topic_ids: dict[str, int] = {}
        program_feature_ids: dict[str, int] = {}
        pending = list(specs)
        while pending:
            ready = [spec for spec in pending if spec.parent_code is None or spec.parent_code in topic_ids]
            if not ready:
                unresolved = ", ".join(f"{spec.code}->{spec.parent_code}" for spec in pending)
                raise ValueError(f"topic hierarchy has missing parents or a cycle: {unresolved}")
            for spec in ready:
                parent_feature_id = (
                    program_feature_ids[spec.parent_code]
                    if spec.parent_code is not None
                    else None
                )
                parent_topic_id = topic_ids.get(spec.parent_code) if spec.parent_code else None
                feature_id = connection.execute(
                    "INSERT INTO features (kind, canonical_code, parent_feature_id) VALUES ('concept', ?, ?)",
                    (spec.canonical_code, parent_feature_id),
                ).lastrowid
                connection.execute(
                    "INSERT INTO feature_labels (feature_id, language, name, description) VALUES (?, 'en', ?, ?)",
                    (feature_id, spec.title, spec.description),
                )
                topic_id = connection.execute(
                    """
                    INSERT INTO syllabus_topics (syllabus_id, parent_topic_id, code, title, description)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (syllabus_id, parent_topic_id, spec.code, spec.title, spec.description),
                ).lastrowid
                connection.execute(
                    "INSERT INTO syllabus_topic_features (syllabus_topic_id, feature_id) VALUES (?, ?)",
                    (topic_id, feature_id),
                )
                feature_ids[spec.canonical_code] = int(feature_id)
                program_feature_ids[spec.code] = int(feature_id)
                topic_ids[spec.code] = int(topic_id)
                pending.remove(spec)
    return feature_ids


def _classify_questions(
    rows: list[sqlite3.Row],
    by_program: dict[tuple[str, str, str], list[TopicSpec]],
    feature_ids: dict[str, int],
) -> dict[int, list[tuple[int, float, bool]]]:
    tags: dict[int, list[tuple[int, float, bool]]] = {}
    for row in rows:
        content = str(row["content"] or "").casefold()
        component = _component_family(row["component"])
        matches: list[tuple[int, float, bool]] = []
        program_key = (str(row["qualification"]), str(row["exam_board"]), str(row["course_code"]))
        for spec in by_program.get(program_key, []):
            if spec.components and component not in spec.components:
                continue
            hits = sum(1 for term in spec.terms if _contains_term(content, term))
            if spec.broad or hits:
                feature_id = feature_ids.get(spec.canonical_code)
                if feature_id is not None:
                    weight = 0.35 if spec.broad else min(1.0, 0.55 + 0.15 * hits)
                    matches.append((feature_id, weight, spec.broad))
        if matches:
            tags[int(row["id"])] = matches
    return tags


def _build_similarities(
    rows: list[sqlite3.Row],
    tags: dict[int, list[tuple[int, float, bool]]],
    *,
    top_k: int,
) -> list[tuple[tuple[int, int], int, float]]:
    output: list[tuple[tuple[int, int], int, float]] = []
    counters = {
        int(row["id"]): Counter(_tokenize(str(row["content"])))
        for row in rows
        if str(row["content"] or "").strip()
    }
    document_frequency = Counter(term for counter in counters.values() for term in counter)
    total = len(counters)
    vectors: dict[int, dict[str, float]] = {}
    postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for question_id, counter in counters.items():
        vector = {
            term: (1.0 + math.log(count)) * (math.log((1 + total) / (1 + document_frequency[term])) + 1.0)
            for term, count in counter.items()
            if document_frequency[term] <= max(200, total // 5)
        }
        norm = math.sqrt(sum(value * value for value in vector.values())) or 1.0
        vectors[question_id] = {term: value / norm for term, value in vector.items()}
        for term, value in vectors[question_id].items():
            postings[term].append((question_id, value))

    row_by_question = {int(row["id"]): row for row in rows}
    paper_by_question = {question_id: int(row["paper_id"]) for question_id, row in row_by_question.items()}
    feature_sets = {qid: {feature_id for feature_id, _, _ in values} for qid, values in tags.items()}
    feature_questions: dict[int, list[int]] = defaultdict(list)
    component_questions: dict[tuple[str, str, str, str], list[int]] = defaultdict(list)
    program_questions: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    all_question_ids = list(row_by_question)
    for question_id, row in row_by_question.items():
        for feature_id in feature_sets.get(question_id, set()):
            feature_questions[feature_id].append(question_id)
        program_key = (str(row["qualification"]), str(row["exam_board"]), str(row["course_code"]))
        program_questions[program_key].append(question_id)
        component_questions[(*program_key, _component_family(row["component"]))].append(question_id)

    for source_id in all_question_ids:
        vector = vectors.get(source_id, {})
        scores: Counter[int] = Counter()
        for term, source_weight in vector.items():
            for target_id, target_weight in postings[term]:
                if target_id != source_id and paper_by_question[target_id] != paper_by_question[source_id]:
                    scores[target_id] += source_weight * target_weight
        source_features = feature_sets.get(source_id, set())
        ranked: list[tuple[float, int]] = []
        for target_id, lexical_score in scores.items():
            target_features = feature_sets.get(target_id, set())
            union = source_features | target_features
            topic_score = len(source_features & target_features) / len(union) if union else 0.0
            score = 0.75 * lexical_score + 0.25 * topic_score
            if score >= 0.08:
                ranked.append((score, target_id))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        ranked = ranked[:top_k]
        selected = {target_id for _, target_id in ranked}
        source_row = row_by_question[source_id]
        program_key = (
            str(source_row["qualification"]),
            str(source_row["exam_board"]),
            str(source_row["course_code"]),
        )
        fallback_groups = chain(
            (feature_questions[feature_id] for feature_id in source_features),
            (component_questions[(*program_key, _component_family(source_row["component"]))],),
            (program_questions[program_key],),
            (all_question_ids,),
        )
        for candidates in fallback_groups:
            for target_id in candidates:
                if len(ranked) >= top_k:
                    break
                if (
                    target_id == source_id
                    or target_id in selected
                    or paper_by_question[target_id] == paper_by_question[source_id]
                ):
                    continue
                target_features = feature_sets.get(target_id, set())
                union = source_features | target_features
                topic_score = len(source_features & target_features) / len(union) if union else 0.0
                ranked.append((max(0.01, 0.25 * topic_score), target_id))
                selected.add(target_id)
            if len(ranked) >= top_k:
                break
        for rank, (score, target_id) in enumerate(ranked, 1):
            output.append(((source_id, target_id), rank, round(score, 6)))
    return output


def _write_algorithm(connection: sqlite3.Connection, top_k: int) -> int:
    return int(connection.execute(
        """
        INSERT INTO similarity_algorithms (name, version, configuration_json)
        VALUES (?, ?, ?)
        """,
        (
            ALGORITHM_NAME,
            ALGORITHM_VERSION,
            json.dumps({
                "fallback": "topic_component_program_global",
                "scope": "global",
                "text_weight": 0.75,
                "topic_weight": 0.25,
                "top_k": top_k,
            }, sort_keys=True),
        ),
    ).lastrowid)


def _component_family(value: object) -> str:
    match = re.search(r"\d+", str(value or ""))
    if match is None:
        return ""
    family = str(int(match.group(0)))[0]
    # Pre-2020 Mathematics used Paper 7 for the content now assessed as Paper 6.
    return "6" if family == "7" else family


def _contains_term(content: str, term: str) -> bool:
    if not term:
        return False
    if re.fullmatch(r"[a-z0-9']+", term):
        return re.search(rf"\b{re.escape(term)}\b", content) is not None
    return term in content


def _tokenize(content: str) -> list[str]:
    return [token for token in _TOKEN.findall(content.casefold()) if token not in _STOP_WORDS]
