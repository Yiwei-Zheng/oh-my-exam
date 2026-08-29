from __future__ import annotations

from pathlib import Path
import sqlite3

from fastapi.testclient import TestClient
import pymupdf

from oh_my_exam.config import Settings
from oh_my_exam.main import create_app
from oh_my_exam.paper_store import FileSystemPaperStore, PaperNotFoundError


def _create_global_database(path: Path) -> None:
    path.parent.mkdir(parents=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE exam_boards (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
            INSERT INTO exam_boards VALUES (1, 'uat', 'UAT-UK');
            CREATE TABLE qualifications (id INTEGER PRIMARY KEY, code TEXT, name TEXT);
            INSERT INTO qualifications VALUES (1, 'admissions', 'Admissions');
            CREATE TABLE exam_programs (
                id INTEGER PRIMARY KEY, exam_board_id INTEGER, qualification_id INTEGER,
                code TEXT, name TEXT
            );
            INSERT INTO exam_programs VALUES (1, 1, 1, 'engaa', 'ENGAA');
            CREATE TABLE papers (
                id INTEGER PRIMARY KEY, exam_program_id INTEGER, stable_key TEXT,
                source_key TEXT, year INTEGER, session TEXT
            );
            INSERT INTO papers VALUES (1, 1, 'admissions:uat:engaa:engaa_2023_s1_qp', 'engaa_2023_s1_qp', 2023, 'summer');
            CREATE TABLE paper_documents (
                id INTEGER PRIMARY KEY, paper_id INTEGER, role TEXT, storage_key TEXT,
                original_filename TEXT
            );
            INSERT INTO paper_documents VALUES (
                1, 1, 'question_paper', 'uat/admissions/engaa/2023/engaa_2023_s1_qp.pdf', 'engaa_2023_s1_qp.pdf'
            );
            INSERT INTO paper_documents VALUES (
                2, 1, 'answer_key', 'uat/admissions/engaa/2023/engaa_2023_s1_ms.pdf', 'engaa_2023_s1_ms.pdf'
            );
            CREATE TABLE questions (
                id INTEGER PRIMARY KEY, paper_id INTEGER, stable_key TEXT, local_key TEXT,
                question_number TEXT, sort_order INTEGER
            );
            INSERT INTO questions VALUES (
                7, 1, 'admissions:uat:engaa:engaa_2023_s1_qp:q07', 'q07', '7', 7
            );
            CREATE TABLE question_texts (
                question_id INTEGER, text_kind TEXT, language TEXT, content TEXT
            );
            INSERT INTO question_texts VALUES (7, 'search', 'en', 'Find the acceleration of the particle.');
            CREATE TABLE question_regions (
                question_id INTEGER, document_id INTEGER, region_order INTEGER, page_index INTEGER,
                x0 REAL, y0 REAL, x1 REAL, y1 REAL, render_dpi INTEGER, join_gap_px INTEGER,
                post_left INTEGER, post_top INTEGER, post_right INTEGER, post_bottom INTEGER
            );
            INSERT INTO question_regions VALUES (7, 1, 0, 1, 0, 0, 200, 50, 180, 0, NULL, NULL, NULL, NULL);
            CREATE TABLE answers (
                id INTEGER PRIMARY KEY, question_id INTEGER, source_document_id INTEGER,
                answer_kind TEXT
            );
            INSERT INTO answers VALUES (1, 7, 2, 'answer_key');
            CREATE TABLE answer_regions (
                answer_id INTEGER, region_order INTEGER, page_index INTEGER,
                x0 REAL, y0 REAL, x1 REAL, y1 REAL, render_dpi INTEGER, join_gap_px INTEGER,
                post_left INTEGER, post_top INTEGER, post_right INTEGER, post_bottom INTEGER
            );
            INSERT INTO answer_regions VALUES (1, 0, 1, 0, 0, 200, 50, 180, 0, NULL, NULL, NULL, NULL);
            CREATE TABLE answer_versions (
                id INTEGER PRIMARY KEY, answer_id INTEGER, version INTEGER, language TEXT,
                raw_text TEXT, markdown TEXT, status TEXT
            );
            INSERT INTO answer_versions VALUES (
                1, 1, 1, 'en', 'Acceleration is 2', '**Acceleration is 2**', 'published'
            );
            """
        )


def _client(tmp_path: Path, *, with_admin: bool = False) -> TestClient:
    database_path = tmp_path / "databases" / "global_exam_catalog.sqlite"
    paper_root = tmp_path / "raw_papers"
    _create_global_database(database_path)
    paper_dir = paper_root / "uat" / "admissions" / "engaa" / "2023"
    paper_dir.mkdir(parents=True)
    _write_pdf(paper_dir / "engaa_2023_s1_qp.pdf", "Question page", "Find the acceleration")
    _write_pdf(paper_dir / "engaa_2023_s1_ms.pdf", "Answer page", "Acceleration is 2")
    settings = Settings(
        tmp_path,
        database_path,
        paper_root,
        app_database_path=tmp_path / "application.sqlite3",
        bootstrap_admin_email="admin@example.com" if with_admin else "",
        bootstrap_admin_password="a-long-test-password" if with_admin else "",
    )
    return TestClient(create_app(settings))


def _write_pdf(path: Path, first_page: str, second_page: str) -> None:
    document = pymupdf.open()
    try:
        document.new_page(width=200, height=100).insert_text((10, 20), first_page)
        document.new_page(width=200, height=100).insert_text((10, 20), second_page)
        document.save(path)
    finally:
        document.close()


def test_catalog_question_and_local_pdf_endpoints(tmp_path: Path) -> None:
    client = _client(tmp_path)

    exams = client.get("/api/v1/exams")
    assert exams.status_code == 200
    assert exams.json()[0]["id"] == "admissions:uat:engaa"
    assert exams.json()[0]["question_count"] == 1

    questions = client.get("/api/v1/exams/admissions:uat:engaa/questions", params={"query": "acceleration"})
    assert questions.status_code == 200
    assert questions.json()[0]["id"] == 7

    question = client.get("/api/v1/exams/admissions:uat:engaa/questions/7")
    assert question.status_code == 200
    assert question.json()["crop_regions"][0]["render_dpi"] == 180
    assert question.json()["answer_structured"]["raw_text"] == "Acceleration is 2"

    question_pdf = client.get("/api/v1/exams/admissions:uat:engaa/questions/7/question.pdf")
    assert question_pdf.status_code == 200
    assert question_pdf.headers["content-type"] == "application/pdf"
    assert question_pdf.headers["content-disposition"] == 'inline; filename="engaa_2023_s1_qp_q07.pdf"'
    with pymupdf.open(stream=question_pdf.content, filetype="pdf") as cropped:
        assert cropped.page_count == 1
        assert cropped[0].rect.width == 200
        assert cropped[0].rect.height == 50
        assert "Find the acceleration" in cropped[0].get_text()

    answer_pdf = client.get("/api/v1/exams/admissions:uat:engaa/questions/7/answer.pdf")
    assert answer_pdf.status_code == 200
    with pymupdf.open(stream=answer_pdf.content, filetype="pdf") as cropped:
        assert "Acceleration is 2" in cropped[0].get_text()

    paper = client.get("/api/v1/exams/admissions:uat:engaa/papers/1/question")
    assert paper.status_code == 200
    assert paper.headers["content-type"] == "application/pdf"
    assert paper.content.startswith(b"%PDF")

    paper_range = client.get(
        "/api/v1/exams/admissions:uat:engaa/papers/1/question",
        headers={"Range": "bytes=0-3"},
    )
    assert paper_range.status_code == 206
    assert paper_range.content == b"%PDF"

    unsupported_kind = client.get("/api/v1/exams/admissions:uat:engaa/papers/1/upstream-url")
    assert unsupported_kind.status_code == 404


def test_capabilities_and_placeholders_are_explicit(tmp_path: Path) -> None:
    client = _client(tmp_path)

    capabilities = client.get("/api/v1/capabilities").json()
    assert capabilities["catalog"]["status"] == "ready"
    assert capabilities["authentication"]["status"] == "ready"
    assert capabilities["question_update"]["status"] == "needs_configuration"
    assert capabilities["tmua_data"]["status"] == "missing"

    response = client.post("/api/v1/math/evaluate", json={"input": "x + x"})
    assert response.status_code == 501
    assert response.json()["capability"] == "math_harness"


def test_admin_login_statistics_and_question_tree(tmp_path: Path) -> None:
    client = _client(tmp_path, with_admin=True)

    unauthorized = client.get("/api/v1/admin/statistics")
    assert unauthorized.status_code == 401

    invalid = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "wrong"},
    )
    assert invalid.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ADMIN@example.com", "password": "a-long-test-password"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "admin"
    assert login.cookies.get("ome_session")

    stats = client.get("/api/v1/admin/statistics")
    assert stats.status_code == 200
    assert stats.json()["users_total"] == 1
    assert stats.json()["active_7d"] == 1

    created = client.post(
        "/api/v1/admin/users",
        json={
            "email": "second-admin@example.com",
            "password": "a-second-long-test-password",
            "role": "admin",
        },
    )
    assert created.status_code == 201
    assert created.json()["user"]["role"] == "admin"
    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200
    assert {user["email"] for user in users.json()["users"]} == {
        "admin@example.com",
        "second-admin@example.com",
    }
    assert "password" not in created.json()["user"]
    duplicate = client.post(
        "/api/v1/admin/users",
        json={
            "email": "SECOND-ADMIN@example.com",
            "password": "another-long-test-password",
            "role": "admin",
        },
    )
    assert duplicate.status_code == 409

    invitation = client.post(
        "/api/v1/admin/invitations",
        json={"role": "student", "max_uses": 1, "expires_in_days": 14},
    )
    assert invitation.status_code == 201
    invitation_code = invitation.json()["code"]
    assert invitation_code.startswith("OME-")
    assert invitation.json()["invitation"]["role"] == "student"
    listed_invitations = client.get("/api/v1/admin/invitations")
    assert listed_invitations.status_code == 200
    assert listed_invitations.json()["invitations"][0]["code_hint"] == invitation_code[-6:]
    assert "code" not in listed_invitations.json()["invitations"][0]

    registered = TestClient(client.app).post(
        "/api/v1/auth/register",
        json={
            "email": "student@example.com",
            "password": "student-long-test-password",
            "invitation_code": invitation_code.lower(),
        },
    )
    assert registered.status_code == 201
    assert registered.json()["user"]["role"] == "student"
    reused = TestClient(client.app).post(
        "/api/v1/auth/register",
        json={
            "email": "another-student@example.com",
            "password": "student-long-test-password",
            "invitation_code": invitation_code,
        },
    )
    assert reused.status_code == 422

    tree = client.get("/api/v1/admin/question-tree")
    assert tree.status_code == 200
    paper_node = tree.json()[0]["children"][0]["children"][0]["children"][0]["children"][0]["children"][0]
    assert paper_node["count"] == 1
    assert paper_node["exam_id"] == "admissions:uat:engaa"

    paper_questions = client.get("/api/v1/admin/papers/1/questions")
    assert paper_questions.status_code == 200
    assert paper_questions.json()[0]["question_number"] == "7"

    revision = client.patch(
        "/api/v1/admin/questions/7/answer-text",
        json={"raw_text": "Updated raw", "markdown": "**Updated**"},
    )
    assert revision.status_code == 200
    assert revision.json()["answer_structured"]["version"] == 2
    updated_question = client.get("/api/v1/exams/admissions:uat:engaa/questions/7")
    assert updated_question.json()["answer_structured"]["markdown"] == "**Updated**"

    update = client.post("/api/v1/admin/question-update")
    assert update.status_code == 503

    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401


def test_login_endpoint_throttles_repeated_account_guesses(tmp_path: Path) -> None:
    client = _client(tmp_path, with_admin=True)

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "invalid_credentials"}

    throttled = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "a-long-test-password"},
    )
    assert throttled.status_code == 429
    assert throttled.json() == {"detail": "too_many_login_attempts"}
    assert 1 <= int(throttled.headers["retry-after"]) <= 15 * 60


def test_paper_store_rejects_globs_and_paths(tmp_path: Path) -> None:
    store = FileSystemPaperStore(tmp_path)
    for unsafe_stem in ("../paper.pdf", "folder/../../paper.pdf", "C:/paper.pdf"):
        try:
            store.find_by_storage_key(unsafe_stem)
        except PaperNotFoundError:
            continue
        raise AssertionError(f"unsafe stem was accepted: {unsafe_stem}")


def test_api_does_not_serve_frontend_or_repository_files(tmp_path: Path) -> None:
    database_path = tmp_path / "databases" / "global_exam_catalog.sqlite"
    _create_global_database(database_path)
    settings = Settings(
        tmp_path,
        database_path,
        tmp_path / "raw_papers",
        app_database_path=tmp_path / "application.sqlite3",
    )
    client = TestClient(create_app(settings))

    assert client.get("/").status_code == 404
    assert client.get("/admin").status_code == 404
    assert client.get("/assets/app.js").status_code == 404
    assert client.get("/api/v1/unknown").status_code == 404
    assert client.get("/%2e%2e/pyproject.toml").status_code == 404
