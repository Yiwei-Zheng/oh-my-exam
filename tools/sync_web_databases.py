from __future__ import annotations

import argparse
from dataclasses import dataclass
import filecmp
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT / "data" / "databases"
DEFAULT_RUNTIME = PROJECT_ROOT / "web" / "public" / "runtime"
DEFAULT_LABELS = PROJECT_ROOT / "configs" / "web_subject_labels.json"

MESSAGES = {
    "zh": {
        "description": "把 data/databases 中的题库同步到网页静态运行时。",
        "done": "同步完成：{total} 个题库，复制 {copied} 个，未变化 {unchanged} 个，删除过期副本 {removed} 个。",
    },
    "en": {
        "description": "Synchronize data/databases into the web static runtime.",
        "done": "Sync complete: {total} databases, {copied} copied, {unchanged} unchanged, {removed} stale copies removed.",
    },
}


@dataclass(frozen=True)
class DatabaseAsset:
    source: Path
    filename: str
    qualification: str
    exam_board: str
    course_code: str
    course_display_name: str


@dataclass(frozen=True)
class SyncSummary:
    total: int
    copied: int
    unchanged: int
    removed: int
    manifest_path: Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=MESSAGES["zh"]["description"])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--runtime", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    return parser


def sync_databases(source_root: Path, runtime_root: Path, labels_path: Path) -> SyncSummary:
    source_root = source_root.resolve()
    runtime_root = runtime_root.resolve()
    if not source_root.is_dir():
        raise FileNotFoundError(f"database source directory does not exist: {source_root}")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    assets = [_read_database(path) for path in sorted(source_root.rglob("*.sqlite"))]
    filenames = [asset.filename for asset in assets]
    if len(filenames) != len(set(filenames)):
        raise ValueError("database filenames must be unique across data/databases")

    database_root = runtime_root / "databases"
    database_root.mkdir(parents=True, exist_ok=True)
    copied = 0
    unchanged = 0
    for asset in assets:
        destination = database_root / asset.filename
        if destination.exists() and filecmp.cmp(asset.source, destination, shallow=False):
            unchanged += 1
            continue
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            shutil.copy2(asset.source, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        copied += 1

    expected = set(filenames)
    removed = 0
    for stale in database_root.glob("*.sqlite"):
        if stale.name not in expected:
            stale.unlink()
            removed += 1

    subjects = [_subject_entry(asset, labels) for asset in assets]
    subjects.sort(key=lambda item: item["id"])
    manifest_path = runtime_root / "subjects.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_manifest = manifest_path.with_suffix(".json.part")
    temporary_manifest.write_text(
        json.dumps(subjects, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary_manifest, manifest_path)
    return SyncSummary(len(assets), copied, unchanged, removed, manifest_path)


def _read_database(path: Path) -> DatabaseAsset:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    try:
        with sqlite3.connect(uri, uri=True) as connection:
            row = connection.execute(
                "SELECT qualification, exam_board, course_code, course_display_name "
                "FROM database_info LIMIT 1"
            ).fetchone()
    except sqlite3.Error as exc:
        raise ValueError(f"invalid subject database {path}: {exc}") from exc
    if row is None or not all(isinstance(value, str) and value.strip() for value in row[:3]):
        raise ValueError(f"invalid database_info in {path}")
    qualification, exam_board, course_code, display_name = (str(value).strip() for value in row)
    return DatabaseAsset(path.resolve(), path.name, qualification, exam_board, course_code, display_name)


def _subject_entry(asset: DatabaseAsset, labels: dict[str, object]) -> dict[str, object]:
    qualification_names = labels.get("qualifications", {})
    exam_board_names = labels.get("exam_boards", {})
    course_names = labels.get("courses", {})
    source_stat = asset.source.stat()
    version = f"{source_stat.st_size}-{source_stat.st_mtime_ns // 1_000_000}"
    return {
        "id": f"{asset.qualification}:{asset.exam_board}:{asset.course_code}",
        "qualification": {
            "id": asset.qualification,
            "name": qualification_names.get(
                asset.qualification,
                {"zh": asset.qualification, "en": asset.qualification},
            ),
        },
        "examBoard": {
            "id": asset.exam_board,
            "name": exam_board_names.get(
                asset.exam_board,
                {"zh": asset.exam_board.upper(), "en": asset.exam_board.upper()},
            ),
        },
        "courseCode": asset.course_code,
        "name": course_names.get(
            asset.course_code,
            {"zh": asset.course_display_name, "en": asset.course_display_name},
        ),
        "filename": asset.filename,
        "databaseUrl": f"/runtime/databases/{asset.filename}?v={version}",
    }


def main(argv: Sequence[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    summary = sync_databases(args.source, args.runtime, args.labels)
    print(MESSAGES[args.lang]["done"].format(**summary.__dict__))


if __name__ == "__main__":
    main()
