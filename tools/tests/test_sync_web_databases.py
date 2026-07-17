from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sync_web_databases import sync_databases  # noqa: E402


def _database(path: Path, qualification: str, exam_board: str, course_code: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE database_info (qualification TEXT, exam_board TEXT, "
            "course_code TEXT, course_display_name TEXT)"
        )
        connection.execute(
            "INSERT INTO database_info VALUES (?, ?, ?, ?)",
            (qualification, exam_board, course_code, course_code.upper()),
        )


def test_sync_databases_copies_assets_writes_manifest_and_removes_stale_files(tmp_path: Path) -> None:
    source = tmp_path / "data" / "databases"
    runtime = tmp_path / "web" / "public" / "runtime"
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps({
            "qualifications": {"a_level": {"zh": "A Level", "en": "A Level"}},
            "exam_boards": {"cie": {"zh": "CIE", "en": "CIE"}},
            "courses": {"9231": {"zh": "进阶数学", "en": "Further Mathematics"}},
        }),
        encoding="utf-8",
    )
    database = source / "a_level" / "cie" / "cie_a_level_9231.sqlite"
    _database(database, "a_level", "cie", "9231")
    stale = runtime / "databases" / "stale.sqlite"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"stale")

    first = sync_databases(source, runtime, labels)
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert first.copied == 1
    assert first.removed == 1
    assert manifest[0]["id"] == "a_level:cie:9231"
    assert manifest[0]["name"]["en"] == "Further Mathematics"
    assert manifest[0]["databaseUrl"].startswith(
        "/runtime/databases/cie_a_level_9231.sqlite?v="
    )
    assert (runtime / "databases" / database.name).read_bytes() == database.read_bytes()

    second = sync_databases(source, runtime, labels)
    assert second.copied == 0
    assert second.unchanged == 1
