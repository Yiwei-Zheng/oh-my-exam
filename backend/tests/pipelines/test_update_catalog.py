from __future__ import annotations

from pathlib import Path

from oh_my_exam.pipelines import update_catalog


def test_update_catalog_continues_after_one_project_fails(monkeypatch, tmp_path: Path) -> None:
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

    result = update_catalog.update_catalog(tmp_path, ["ocr:step", "uat:engaa"], 2)

    assert result == active
    assert calls == ["pack", "release"]
