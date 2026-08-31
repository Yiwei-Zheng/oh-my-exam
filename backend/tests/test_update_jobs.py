from __future__ import annotations

from pathlib import Path
import json
import time
from threading import Event

import pytest

from oh_my_exam.update_jobs import UpdateJobManager


def test_update_workflows_only_expose_complete_subject_pipelines(tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())

    assert [item["id"] for item in manager.workflows()] == [
        "cie:9709",
        "cie:9231",
        "ocr:step",
        "uat:engaa",
        "uat:nsaa",
        "uat:tmua",
    ]
    assert all(item["status"] == "ready" for item in manager.workflows())


def test_update_probe_compares_selected_subjects(monkeypatch, tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())
    monkeypatch.setattr(
        manager,
        "_probe_cie",
        lambda subject_ids, _root: [
            {
                "id": f"{subject_ids[0]}:local",
                "subject_id": subject_ids[0],
                "label": "local",
                "year": 2025,
                "document_type": "qp",
                "local": True,
            },
            {
                "id": f"{subject_ids[0]}:new",
                "subject_id": subject_ids[0],
                "label": "new",
                "year": 2026,
                "document_type": "ms",
                "local": False,
            },
        ],
    )

    result = manager.probe(["cie:9709"], tmp_path)

    assert result["resource_count"] == 2
    assert result["local_count"] == 1
    assert result["new_count"] == 1
    assert result["new_resources"][0]["label"] == "new"


def test_update_probe_isolates_subject_discovery_failures(monkeypatch, tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())
    calls: list[list[str]] = []

    def probe_cie(subject_ids, _root):
        calls.append(list(subject_ids))
        if subject_ids == ["cie:9709"]:
            raise RuntimeError("Frank unavailable")
        return []

    monkeypatch.setattr(manager, "_probe_cie", probe_cie)

    result = manager.probe(["cie:9709", "cie:9231"], tmp_path)

    assert calls == [["cie:9709"], ["cie:9231"]]
    assert result["errors"] == [{"subject_id": "cie:9709", "message": "Frank unavailable"}]


def test_update_probe_routes_each_exam_family_to_its_source(monkeypatch, tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())
    calls: list[str] = []
    monkeypatch.setattr(manager, "_probe_step", lambda _root: calls.append("step") or [])
    monkeypatch.setattr(
        manager,
        "_probe_uat",
        lambda subject_id, _root: calls.append(subject_id) or [],
    )

    manager.probe(["ocr:step", "uat:engaa", "uat:nsaa", "uat:tmua"], tmp_path)

    assert calls == ["step", "uat:engaa", "uat:nsaa", "uat:tmua"]


def test_update_rejects_unknown_or_empty_subject_selection(tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())

    with pytest.raises(ValueError, match="select_at_least_one_subject"):
        manager.probe([], tmp_path)
    with pytest.raises(ValueError, match="unknown_update_subjects"):
        manager.probe(["cie:0000"], tmp_path)


def test_update_rejects_unknown_stage_or_mode(tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ("update",))

    with pytest.raises(ValueError, match="unknown_update_stage"):
        manager.start(1, ["cie:9709"], stage="publish")
    with pytest.raises(ValueError, match="unknown_update_mode"):
        manager.start(1, ["cie:9709"], mode="append")


def test_probe_runs_as_a_background_job(monkeypatch, tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())
    with manager._connect() as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO users (id) VALUES (1)")
    monkeypatch.setattr(manager, "_probe_cie", lambda _subjects, _root: [])

    job = manager.start_probe(1, ["cie:9709"], tmp_path)

    assert job["action"] == "probe"
    deadline = time.monotonic() + 2
    while (latest := manager.latest())["status"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    assert latest["status"] == "completed"
    assert latest["result"]["resource_count"] == 0


def test_probe_job_can_pause_and_resume_between_subjects(monkeypatch, tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())
    with manager._connect() as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO users (id) VALUES (1)")
    entered = Event()
    release = Event()

    def probe_cie(_subjects, _root):
        entered.set()
        assert release.wait(1)
        return []

    monkeypatch.setattr(manager, "_probe_cie", probe_cie)
    job = manager.start_probe(1, ["cie:9709", "cie:9231"], tmp_path)
    assert entered.wait(1)

    paused = manager.pause(int(job["id"]))
    release.set()
    time.sleep(0.05)

    assert paused["paused"] is True
    assert manager.get(int(job["id"]))["status"] == "running"
    resumed = manager.resume(int(job["id"]))
    assert resumed["paused"] is False

    deadline = time.monotonic() + 2
    while (
        (latest := manager.get(int(job["id"]))).get("status") == "running"
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert latest["status"] == "completed"
    assert latest["paused"] is False


def test_job_progress_does_not_move_backwards(tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ())
    with manager._connect() as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO users (id) VALUES (1)")
        cursor = connection.execute(
            """
            INSERT INTO question_update_jobs
                (requested_by, status, stage, action, progress, message)
            VALUES (1, 'running', 'classifying', 'search', 82, 'publishing')
            """
        )
        job_id = int(cursor.lastrowid)

    manager._consume_progress(
        job_id,
        json.dumps({"stage": "checking", "progress": 8, "message": "validating"}),
    )

    job = manager.get(job_id)
    assert job["stage"] == "classifying"
    assert job["progress"] == 82


def test_update_subprocess_uses_utf8_and_reports_eta(monkeypatch, tmp_path: Path) -> None:
    manager = UpdateJobManager(tmp_path / "app.sqlite3", ("update",))
    with manager._connect() as connection:
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO users (id) VALUES (1)")
        cursor = connection.execute(
            """
            INSERT INTO question_update_jobs
                (requested_by, status, stage, action, progress, message, started_at)
            VALUES (1, 'running', 'downloading', 'all', 25, '', datetime('now', '-100 seconds'))
            """
        )
        job_id = int(cursor.lastrowid)

    captured: dict[str, object] = {}

    class Process:
        stdout = [json.dumps({"stage": "downloading", "progress": 25, "message": "正在下载试卷"}, ensure_ascii=False)]

        @staticmethod
        def wait() -> int:
            return 0

    def popen(*_args, **kwargs):
        captured.update(kwargs)
        return Process()

    monkeypatch.setattr("oh_my_exam.update_jobs.subprocess.Popen", popen)

    running = manager.get(job_id)
    manager._run(job_id, ["cie:9709"], 16, "all", "update")

    environment = captured["env"]
    assert isinstance(environment, dict)
    assert environment["PYTHONUTF8"] == "1"
    assert environment["PYTHONIOENCODING"] == "utf-8"
    assert captured["encoding"] == "utf-8"
    assert captured["errors"] == "strict"
    assert 95 <= running["elapsed_seconds"] <= 105
    assert 285 <= running["eta_seconds"] <= 315
    assert manager.get(job_id)["message"] == "正在下载试卷"
