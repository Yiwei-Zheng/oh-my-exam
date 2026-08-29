from __future__ import annotations

import argparse
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Sequence

from oh_my_exam.pipelines.adapters.pat.splitter.cutter import SplitOptions
from oh_my_exam.pipelines.adapters.pat.splitter.pipeline import split_downloaded


MESSAGES = {
    "zh": {"description": "PAT 历年卷与解析切题工具。", "done": "切题统计: {counts}"},
    "en": {"description": "Split PAT papers and paired solutions.", "done": "split counts: {counts}"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pat-admissions-splitter", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--variant", action="append", choices=["regular", "specimen"], dest="variants")
    parser.add_argument("--document-type", action="append", choices=["qp", "ms"], dest="document_types")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    parser.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "data/reports/pat_admissions_split.jsonl")
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--quality", type=int, default=90)
    parser.add_argument("--ocr-dpi", type=int, default=150)
    parser.add_argument("--cpu-only", action="store_true")
    parser.add_argument("--limit", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    counts = split_downloaded(
        args.raw_root,
        args.processed_root,
        args.report,
        variants=set(args.variants) if args.variants else None,
        document_types=set(args.document_types) if args.document_types else None,
        start_year=args.start_year,
        end_year=args.end_year,
        limit=args.limit,
        options=SplitOptions(dpi=args.dpi, quality=args.quality, ocr_dpi=args.ocr_dpi, prefer_gpu=not args.cpu_only),
        progress=lambda record: print(f"{record['asset']}: {record['status']}"),
    )
    print(MESSAGES[args.lang]["done"].format(counts=counts))


if __name__ == "__main__":
    main()
