from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from uat_admissions_downloader.catalog import DEFAULT_ARCHIVE_URLS, discover_assets
from uat_admissions_downloader.download import download_assets


MESSAGES = {
    "zh": {"description": "从 UAT-UK 官网下载 ENGAA/NSAA/TMUA 历年卷。", "found": "发现 {count} 个官方 PDF", "done": "下载统计: {counts}"},
    "en": {"description": "Download the official UAT-UK ENGAA/NSAA/TMUA archive.", "found": "found {count} official PDFs", "done": "download counts: {counts}"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uat-admissions-downloader", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh")
    parser.add_argument("--archive-url", action="append", dest="archive_urls")
    parser.add_argument("--exam", action="append", choices=["engaa", "nsaa", "tmua"], dest="exams")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw_papers"))
    parser.add_argument("--report", type=Path, default=Path("data/reports/uat_admissions_download.jsonl"))
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--list-only", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    messages = MESSAGES[args.lang]
    exams = set(args.exams or ("engaa", "nsaa"))
    archive_urls = args.archive_urls or [
        url for url in DEFAULT_ARCHIVE_URLS
        if ("tmua-preparation" in url and "tmua" in exams)
        or ("esat-preparation" in url and exams.intersection({"engaa", "nsaa"}))
    ]
    assets = [asset for url in archive_urls for asset in discover_assets(url)]
    assets = [
        asset for asset in assets
        if asset.exam in exams
        and (asset.year is None or args.start_year is None or asset.year >= args.start_year)
        and (asset.year is None or args.end_year is None or asset.year <= args.end_year)
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
        counts = download_assets(assets, args.raw_root, delay_seconds=args.delay, progress=lambda item: report.write(json.dumps(item, ensure_ascii=False) + "\n"))
    print(messages["done"].format(counts=counts))


if __name__ == "__main__":
    main()
