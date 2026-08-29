from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
TOOL_SRC = ROOT / "tools" / "packers" / "src"
if str(TOOL_SRC) not in sys.path:
    sys.path.insert(0, str(TOOL_SRC))

from exam_packer.global_migration import GlobalMigrationOptions, migrate_portable_catalogs
from exam_packer.answer_extraction import extract_answer_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ome-global-catalog",
        description="将现有单科 SQLite 迁移为统一的全局题库。",
    )
    parser.add_argument("--database-root", type=Path, default=Path("data/databases"))
    parser.add_argument("--paper-root", type=Path, default=Path("data/raw_papers"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/databases/global_exam_catalog.sqlite"),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--strip-legacy-urls",
        action="store_true",
        help="迁移成功后删除旧单科数据库中的 URL 列。",
    )
    parser.add_argument(
        "--extract-answer-text",
        action="store_true",
        help="使用答案裁剪区域从本地 PDF 提取 Markdown 草稿。",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    summary = migrate_portable_catalogs(
        GlobalMigrationOptions(
            database_root=args.database_root,
            paper_root=args.paper_root,
            output_path=args.output,
            overwrite=args.overwrite,
            strip_legacy_urls=args.strip_legacy_urls,
        )
    )
    for line in summary.as_lines():
        print(line)
    if args.extract_answer_text:
        answer_summary = extract_answer_markdown(
            args.output,
            args.paper_root,
            overwrite=args.overwrite,
        )
        print(f"answers_seen={answer_summary.answers_seen}")
        print(f"answer_versions_written={answer_summary.versions_written}")
        print(f"empty_answers={answer_summary.empty_answers}")
    print(f"database_path={args.output.resolve()}")


if __name__ == "__main__":
    main()
