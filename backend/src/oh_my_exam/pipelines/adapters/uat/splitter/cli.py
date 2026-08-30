from __future__ import annotations

import argparse
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Sequence

from oh_my_exam.pipelines.adapters.uat.splitter.cutter import SplitOptions
from oh_my_exam.pipelines.adapters.uat.splitter.pipeline import split_downloaded


MESSAGES = {
    "zh": {"description": "ENGAA/NSAA/TMUA 官网卷切题工具。", "done": "切题统计: {counts}"},
    "en": {"description": "Split official ENGAA/NSAA/TMUA papers and answers.", "done": "split counts: {counts}"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uat-admissions-splitter", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--exam", action="append", choices=["engaa", "nsaa", "tmua"], dest="exams")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    parser.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "data/reports/uat_admissions_split.jsonl")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--quality", type=int, default=90)
    parser.add_argument("--limit", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    counts = split_downloaded(
        args.raw_root,
        args.processed_root,
        args.report,
        exams=set(args.exams) if args.exams else None,
        start_year=args.start_year,
        end_year=args.end_year,
        limit=args.limit,
        options=SplitOptions(dpi=args.dpi, quality=args.quality),
        progress=lambda record: print(f"{record['asset']}: {record['status']}"),
    )
    print(MESSAGES[args.lang]["done"].format(counts=counts))


if __name__ == "__main__":
    main()
