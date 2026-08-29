from pathlib import Path
import sqlite3
from types import SimpleNamespace

from oh_my_exam.pipelines import release


def test_build_and_activate_release_replaces_active_catalog(monkeypatch, tmp_path: Path) -> None:
    database_root = tmp_path / "databases"
    paper_root = tmp_path / "raw_papers"
    database_root.mkdir()
    paper_root.mkdir()
    active = database_root / "global_exam_catalog.sqlite"
    active.write_bytes(b"old catalog")

    def fake_migrate(options):
        with sqlite3.connect(options.output_path) as connection:
            connection.execute("CREATE TABLE questions (id INTEGER PRIMARY KEY)")
            connection.execute("INSERT INTO questions DEFAULT VALUES")
        return SimpleNamespace(questions=1)

    monkeypatch.setattr(release, "migrate_portable_catalogs", fake_migrate)
    monkeypatch.setattr(
        release,
        "extract_answer_markdown",
        lambda *_args, **_kwargs: SimpleNamespace(versions_written=0),
    )
    monkeypatch.setattr(
        release,
        "rebuild_question_matching",
        lambda *_args, **_kwargs: SimpleNamespace(tagged_questions=0),
    )

    assert release.build_and_activate_release(tmp_path) == active
    with sqlite3.connect(active) as connection:
        assert connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0] == 1
    assert not (database_root / "global_exam_catalog.candidate.sqlite").exists()


def test_release_parser_accepts_an_explicit_data_root(tmp_path: Path) -> None:
    args = release.build_parser().parse_args(["--data-root", str(tmp_path)])
    assert args.data_root == tmp_path
