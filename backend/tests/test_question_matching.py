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
                    "terms": ["acceleration", "velocity", "displacement"], "parent": "mechanics",
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
    topic_nodes = {item["title"]: item for item in catalog.list_topics("a_level:cie:9709")}
    assert topic_nodes["Kinematics"]["parent_id"] == topic_nodes["Mechanics"]["id"]

    client = TestClient(create_app(Settings(
        tmp_path,
        database,
        tmp_path / "raw_papers",
        app_database_path=tmp_path / "application.sqlite3",
        bootstrap_admin_email="admin@example.com",
        bootstrap_admin_password="a-long-test-password",
    )))
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "a-long-test-password"},
    ).status_code == 200
    assert client.get(
        "/api/v1/questions/search",
        params={"query": "constant acceleration", "exam_id": "a_level:cie:9709"},
    ).json()[0]["id"] == 2
    assert client.get(
        "/api/v1/exams/a_level:cie:9709/questions/1/similar"
    ).json()[0]["id"] == 2


def test_classifies_non_cie_exam_programs_from_catalog_identity(tmp_path: Path) -> None:
    database = tmp_path / "catalog.sqlite"
    topics = tmp_path / "topics.json"
    topics.write_text(json.dumps({
        "courses": [{
            "qualification": "admissions",
            "exam_board": "uat",
            "course_code": "tmua",
            "topics": [
                {"code": "paper_2", "title": "Mathematical Reasoning", "components": ["2"], "broad": True},
                {"code": "logic", "title": "Logic and proof", "components": ["2"], "terms": ["counterexample"]},
            ],
        }],
    }), encoding="utf-8")
    with sqlite3.connect(database) as connection:
        migrate_global_catalog(connection)
        connection.executescript(
            """
            INSERT INTO exam_boards VALUES (1, 'uat', 'UAT-UK');
            INSERT INTO qualifications VALUES (1, 'admissions', 'Admissions');
            INSERT INTO exam_programs VALUES (1, 1, 1, 'tmua', 'TMUA');
            INSERT INTO papers VALUES (1, 1, 'p2', 'tmua_2023_p2_qp', 2023, '2023', 'p2', NULL);
            INSERT INTO questions VALUES (1, 1, 'q1', 'q01', '1', 1, 'unknown', NULL);
            INSERT INTO question_texts VALUES (1, 1, 'search', 'en', 'Which function is a counterexample to the statement?');
            """
        )

    summary = rebuild_question_matching(database, topics)

    assert summary.tagged_questions == 1
    with sqlite3.connect(database) as connection:
        assert {
            row[0]
            for row in connection.execute(
                """SELECT f.canonical_code FROM question_features qf
                   JOIN features f ON f.id = qf.feature_id"""
            )
        } == {
            "syllabus:uat:admissions:tmua:paper_2",
            "syllabus:uat:admissions:tmua:logic",
        }


def test_ocr_similarity_ranks_an_older_tmua_question_before_recent_candidates(
    tmp_path: Path,
) -> None:
    database = tmp_path / "catalog.sqlite"
    target_text = (
        "It is given that the expansion of (ax + b)^3 is 8x^3 - px^2 + 18x, "
        "where a, b and p are real constants. What is the value of p?"
    )
    with sqlite3.connect(database) as connection:
        migrate_global_catalog(connection)
        connection.executescript(
            """
            INSERT INTO exam_boards VALUES (1, 'uat', 'UAT-UK');
            INSERT INTO qualifications VALUES (1, 'admissions', 'Admissions');
            INSERT INTO exam_programs VALUES (1, 1, 1, 'tmua', 'TMUA');
            INSERT INTO papers VALUES (1, 1, 'old', 'tmua_2016_p1_qp', 2016, '2016', 'p1', NULL);
            INSERT INTO questions VALUES (1, 1, 'target', 'q01', '1', 1, 'unknown', NULL);
            """
        )
        connection.execute(
            "INSERT INTO question_texts VALUES (1, 1, 'search', 'en', ?)",
            (target_text,),
        )
        for index in range(2, 32):
            connection.execute(
                "INSERT INTO papers VALUES (?, 1, ?, ?, 2023, '2023', 'p1', NULL)",
                (index, f"recent-{index}", f"tmua_2023_p1_qp_{index}"),
            )
            connection.execute(
                "INSERT INTO questions VALUES (?, ?, ?, 'q01', '1', 1, 'unknown', NULL)",
                (index, index, f"distractor-{index}"),
            )
            connection.execute(
                "INSERT INTO question_texts VALUES (?, ?, 'search', 'en', ?)",
                (index, index, f"Given a different diagram, find the value shown in case {index}."),
            )

    results = GlobalCatalog(database).search_questions(
        "given value",
        exam_id="admissions:uat:tmua",
        limit=5,
        match_all_terms=False,
        similarity_text=target_text,
    )

    assert results[0]["id"] == 1


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
