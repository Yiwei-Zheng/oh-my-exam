from __future__ import annotations

import argparse
import json
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Sequence

from oh_my_exam.pipelines.adapters.pat.downloader.catalog import DEFAULT_ARCHIVE_URL, discover_assets
from oh_my_exam.pipelines.adapters.pat.downloader.download import download_assets


MESSAGES = {
    "zh": {"description": "从 PMT 下载 PAT 历年卷与对应解析。", "found": "发现 {count} 个 PAT PDF", "done": "下载统计: {counts}"},
    "en": {"description": "Download PAT papers and paired solutions from PMT.", "found": "found {count} PAT PDFs", "done": "download counts: {counts}"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pat-admissions-downloader", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--archive-url", default=DEFAULT_ARCHIVE_URL)
    parser.add_argument("--variant", action="append", choices=["regular", "specimen"], dest="variants")
    parser.add_argument("--document-type", action="append", choices=["qp", "ms"], dest="document_types")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    parser.add_argument("--report", type=Path, default=BACKEND_ROOT / "data/reports/pat_admissions_download.jsonl")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--list-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    messages = MESSAGES[args.lang]
    assets = discover_assets(args.archive_url)
    variants = set(args.variants or ("regular", "specimen"))
    document_types = set(args.document_types or ("qp", "ms"))
    assets = [
        asset for asset in assets
        if asset.variant in variants
        and asset.document_type in document_types
        and (args.start_year is None or asset.year >= args.start_year)
        and (args.end_year is None or asset.year <= args.end_year)
    ]
    if args.limit is not None:
        assets = assets[: args.limit]
    print(messages["found"].format(count=len(assets)))
    if args.list_only:
        for asset in assets:
            print(f"{asset.stem}\t{asset.variant}\t{asset.source_url}")
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
