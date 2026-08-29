from __future__ import annotations

import argparse
from pathlib import Path

from oh_my_exam.paths import DATABASE_ROOT, RESOURCE_ROOT
from oh_my_exam.question_matching import rebuild_question_matching


DEFAULT_TOPICS = RESOURCE_ROOT / "question_matching" / "cie_a_level_topics.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build syllabus tags and similar-question matches.")
    parser.add_argument("--database", type=Path, default=DATABASE_ROOT / "global_exam_catalog.sqlite")
    parser.add_argument("--topics", type=Path, default=DEFAULT_TOPICS)
    parser.add_argument("--top-k", type=int, default=12)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    summary = rebuild_question_matching(args.database.resolve(), args.topics.resolve(), top_k=args.top_k)
    for name, value in vars(summary).items():
        print(f"{name}={value}")


if __name__ == "__main__":
    main()
