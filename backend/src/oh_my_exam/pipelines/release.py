from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

from oh_my_exam.paths import DATA_ROOT
from oh_my_exam.pipelines.packaging.answer_extraction import extract_answer_markdown
from oh_my_exam.pipelines.packaging.global_migration import GlobalMigrationOptions, migrate_portable_catalogs


def _progress(stage: str, progress: int, message: str) -> None:
    print(json.dumps({"stage": stage, "progress": progress, "message": message}, ensure_ascii=False), flush=True)


def build_and_activate_release(data_root: Path = DATA_ROOT) -> Path:
    database_root = data_root / "databases"
    paper_root = data_root / "raw_papers"
    active = database_root / "global_exam_catalog.sqlite"
    candidate = database_root / "global_exam_catalog.candidate.sqlite"
    candidate.unlink(missing_ok=True)

    _progress("checking", 8, "正在检查本地数据")
    summary = migrate_portable_catalogs(GlobalMigrationOptions(
        database_root=database_root,
        paper_root=paper_root,
        output_path=candidate,
    ))
    _progress("cataloging", 68, f"已写入 {summary.questions} 道题")
    answers = extract_answer_markdown(candidate, paper_root, overwrite=True)
    _progress("classifying", 90, f"已提取 {answers.versions_written} 份答案文本")

    with closing(sqlite3.connect(candidate)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        question_count = int(connection.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
        if integrity != "ok" or question_count == 0:
            raise RuntimeError(f"candidate validation failed: integrity={integrity}, questions={question_count}")
    os.replace(candidate, active)
    _progress("cataloging", 99, "新题库版本已自动上线")
    return active


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build, validate, and atomically activate the local catalog.",
    )
    parser.add_argument(
        "--data-root",
        type=Path,
        default=DATA_ROOT,
        help="Backend data directory containing databases/ and raw_papers/.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    build_and_activate_release(args.data_root.resolve())


if __name__ == "__main__":
    main()
