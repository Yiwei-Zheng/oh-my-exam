from __future__ import annotations

import argparse
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Sequence

from oh_my_exam.pipelines.adapters.step.splitter.cutter import SplitOptions
from oh_my_exam.pipelines.adapters.step.splitter.pipeline import split_downloaded


MESSAGES = {
    "zh": {"description": "STEP 历年卷与答案切题工具。", "done": "切题统计: {counts}"},
    "en": {"description": "Split STEP papers and pairable answers.", "done": "split counts: {counts}"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="step-admissions-splitter", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--paper", action="append", type=int, choices=[1, 2, 3], dest="papers")
    parser.add_argument("--document-type", action="append", choices=["qp", "ms"], dest="document_types")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    parser.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "data/reports/step_admissions_split.jsonl")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--quality", type=int, default=90)
    parser.add_argument("--ocr-dpi", type=int, default=220)
    parser.add_argument("--limit", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    counts = split_downloaded(
        args.raw_root,
        args.processed_root,
        args.report,
        papers=set(args.papers) if args.papers else None,
        document_types=set(args.document_types) if args.document_types else None,
        start_year=args.start_year,
        end_year=args.end_year,
        limit=args.limit,
        options=SplitOptions(dpi=args.dpi, quality=args.quality, ocr_dpi=args.ocr_dpi),
        progress=lambda record: print(f"{record['asset']}: {record['status']}"),
    )
    print(MESSAGES[args.lang]["done"].format(counts=counts))


if __name__ == "__main__":
    main()
