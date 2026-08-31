from __future__ import annotations

from pathlib import Path

import pytest

from oh_my_exam.pipelines import update_catalog


def test_update_catalog_processes_remaining_projects_then_reports_partial_failure(monkeypatch, tmp_path: Path) -> None:
    active = tmp_path / "databases/global_exam_catalog.sqlite"
    calls: list[str] = []
    monkeypatch.setattr(
        update_catalog,
        "discover_step_assets",
        lambda: (_ for _ in ()).throw(RuntimeError("PMT down")),
    )
    monkeypatch.setattr(update_catalog, "discover_assets", lambda _url: [type("Asset", (), {"exam": "engaa"})()])
    monkeypatch.setattr(
        update_catalog,
        "download_uat_assets",
        lambda *_args, **_kwargs: {"downloaded": 1, "skipped": 0, "failed": 0},
    )
    monkeypatch.setattr(
        update_catalog,
        "split_uat_downloads",
        lambda *_args, **_kwargs: {"split": 1, "failed": 0},
    )
    monkeypatch.setattr(
        update_catalog,
        "pack_subject_database",
        lambda *_args, **_kwargs: calls.append("pack"),
    )
    monkeypatch.setattr(
        update_catalog,
        "build_and_activate_release",
        lambda _root: calls.append("release") or active,
    )

    with pytest.raises(RuntimeError, match="PMT down"):
        update_catalog.update_catalog(tmp_path, ["ocr:step", "uat:engaa"], 2)

    assert calls == ["pack", "pack", "release"]


def test_update_catalog_can_run_one_stage_in_overwrite_mode(monkeypatch, tmp_path: Path) -> None:
    calls: list[object] = []
    monkeypatch.setattr(update_catalog, "discover_step_assets", lambda: ["asset"])
    monkeypatch.setattr(
        update_catalog,
        "download_step_assets",
        lambda *_args, **kwargs: calls.append(kwargs["overwrite"])
        or {"downloaded": 1, "skipped": 0, "failed": 0},
    )
    monkeypatch.setattr(
        update_catalog,
        "split_step_downloads",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("split should not run")),
    )

    result = update_catalog.update_catalog(
        tmp_path,
        ["ocr:step"],
        2,
        stage="download",
        mode="overwrite",
    )

    assert result == tmp_path
    assert calls == [True]
