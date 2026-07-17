from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from step_admissions_downloader.catalog import DEFAULT_ARCHIVE_URL, discover_assets
from step_admissions_downloader.download import download_assets


MESSAGES = {
    "zh": {"description": "从 PMT 下载 STEP 历年卷与可配对答案。", "found": "发现 {count} 个 STEP PDF", "done": "下载统计: {counts}"},
    "en": {"description": "Download STEP papers and pairable answers from PMT.", "found": "found {count} STEP PDFs", "done": "download counts: {counts}"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="step-admissions-downloader", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL)
    parser.add_argument("--paper", action="append", type=int, choices=[1, 2, 3], dest="papers")
    parser.add_argument("--document-type", action="append", choices=["qp", "ms"], dest="document_types")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw_papers"))
    parser.add_argument("--report", type=Path, default=Path("data/reports/step_admissions_download.jsonl"))
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--list-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    messages = MESSAGES[args.lang]
    assets = discover_assets(args.archive_url)
    papers = set(args.papers or (1, 2, 3))
    document_types = set(args.document_types or ("qp", "ms"))
    assets = [
        asset for asset in assets
        if asset.paper in papers
        and asset.document_type in document_types
        and (args.start_year is None or asset.year >= args.start_year)
        and (args.end_year is None or asset.year <= args.end_year)
    ]
    if args.limit is not None:
        assets = assets[: args.limit]
    print(messages["found"].format(count=len(assets)))
    if args.list_only:
        for asset in assets:
            print(f"{asset.stem}\t{asset.source_url}")
        return
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("a", encoding="utf-8") as report:
        counts = download_assets(
            assets,
            args.raw_root,
            delay_seconds=args.delay,
            progress=lambda item: report.write(json.dumps(item, ensure_ascii=False) + "\n"),
        )
    print(messages["done"].format(counts=counts))


if __name__ == "__main__":
    main()
