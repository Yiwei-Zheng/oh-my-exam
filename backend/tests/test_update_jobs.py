from __future__ import annotations

from pathlib import Path

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
