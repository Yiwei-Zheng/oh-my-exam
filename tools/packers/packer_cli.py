from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[2]
TOOL_SRC = ROOT / "tools" / "packers" / "src"
if str(TOOL_SRC) not in sys.path:
    sys.path.insert(0, str(TOOL_SRC))

from exam_packer import PackOptions, pack_subject_database


MESSAGES = {
    "zh": {
        "description": "Oh-My-Exam metadata packer：把 splitter JSON metadata 打包成单科 SQLite。",
        "warning": "警告: {message}",
    },
    "en": {
        "description": "Oh-My-Exam metadata packer: package splitter JSON metadata into one subject SQLite database.",
        "warning": "warning: {message}",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ome-metadata-packer", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言 / Output language.")
    parser.add_argument("--metadata-root", type=Path, default=Path("data/processed_questions"))
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--qualification", required=True)
    parser.add_argument("--exam-board", required=True)
    parser.add_argument("--course-code", required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    output_dir = args.output_dir or Path("data/databases") / args.qualification / args.exam_board
    summary = pack_subject_database(
        PackOptions(
            metadata_root=args.metadata_root,
            output_dir=output_dir,
            qualification=args.qualification,
            exam_board=args.exam_board,
            course_code=args.course_code,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    )
    for warning in summary.warnings:
        print(MESSAGES[args.lang]["warning"].format(message=warning))
    for line in summary.as_lines():
        print(line)


if __name__ == "__main__":
    main()
