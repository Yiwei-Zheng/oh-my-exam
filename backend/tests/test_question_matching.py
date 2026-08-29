from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient

from oh_my_exam.catalog import GlobalCatalog
from oh_my_exam.config import Settings
from oh_my_exam.main import create_app
from oh_my_exam.pipelines.packaging.global_schema import migrate_global_catalog
from oh_my_exam.question_matching import _component_family, rebuild_question_matching


def test_normalizes_historical_and_zero_padded_components() -> None:
    assert _component_family("01") == "1"
    assert _component_family("06") == "6"
    assert _component_family("72") == "6"


def test_builds_syllabus_tags_search_and_similar_questions(tmp_path: Path) -> None:
    database = tmp_path / "catalog.sqlite"
    topics = tmp_path / "topics.json"
    topics.write_text(json.dumps({
        "courses": [{
            "course_code": "9709",
            "topics": [
                {"code": "mechanics", "title": "Mechanics", "components": ["4"], "broad": True},
                {
                    "code": "kinematics", "title": "Kinematics", "components": ["4"],
                    "terms": ["acceleration", "velocity", "displacement"],
                },
            ],
        }],
    }), encoding="utf-8")
    _write_catalog(database)

    summary = rebuild_question_matching(database, topics, top_k=2)

    assert summary.syllabuses == 1
    assert summary.topics == 2
    assert summary.tagged_questions == 3
    assert summary.similarities >= 2
    catalog = GlobalCatalog(database)
    results = catalog.search_questions("acceleration", exam_id="a_level:cie:9709")
    assert [result["id"] for result in results] == [1, 2]
    assert "Kinematics" in results[0]["topics"]
    topic_code = "syllabus:cie:a_level:9709:kinematics"
    assert {item["id"] for item in catalog.search_questions(topic_codes=(topic_code,))} == {1, 2}
    similar = catalog.list_similar_questions("a_level:cie:9709", 1)
    assert similar[0]["id"] == 2
    assert similar[0]["score"] > 0
    assert "Kinematics" in similar[0]["shared_topics"]
    topic_counts = {item["title"]: item["question_count"] for item in catalog.list_topics("a_level:cie:9709")}
    assert topic_counts == {"Kinematics": 2, "Mechanics": 3}

    client = TestClient(create_app(Settings(
        tmp_path,
        database,
        tmp_path / "raw_papers",
        app_database_path=tmp_path / "application.sqlite3",
    )))
    assert client.get(
        "/api/v1/questions/search",
        params={"query": "constant acceleration", "exam_id": "a_level:cie:9709"},
    ).json()[0]["id"] == 2
    assert client.get(
        "/api/v1/exams/a_level:cie:9709/questions/1/similar"
    ).json()[0]["id"] == 2


def _write_catalog(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        migrate_global_catalog(connection)
        connection.executescript(
            """
            INSERT INTO exam_boards VALUES (1, 'cie', 'Cambridge');
            INSERT INTO qualifications VALUES (1, 'a_level', 'A Level');
            INSERT INTO exam_programs VALUES (1, 1, 1, '9709', 'Mathematics');
            INSERT INTO papers VALUES (1, 1, 'p1', '9709_s24_qp_42', 2024, 's24', '42', '2');
            INSERT INTO papers VALUES (2, 1, 'p2', '9709_w24_qp_42', 2024, 'w24', '42', '2');
            INSERT INTO papers VALUES (3, 1, 'p3', '9709_m24_qp_42', 2024, 'm24', '42', '2');
            INSERT INTO questions VALUES (1, 1, 'q1', 'q1', '1', 1, 'unknown', NULL);
            INSERT INTO questions VALUES (2, 2, 'q2', 'q1', '1', 1, 'unknown', NULL);
            INSERT INTO questions VALUES (3, 3, 'q3', 'q1', '1', 1, 'unknown', NULL);
            INSERT INTO question_texts VALUES (1, 1, 'search', 'en', 'Find the acceleration and velocity of the particle.');
            INSERT INTO question_texts VALUES (2, 2, 'search', 'en', 'A particle has constant acceleration. Find its velocity.');
            INSERT INTO question_texts VALUES (3, 3, 'search', 'en', 'A force acts on a particle in equilibrium.');
            """
        )
