from __future__ import annotations

import argparse
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Sequence

from oh_my_exam.pipelines.adapters.cie_alevel.downloader.frank_discovery import (
    DEFAULT_AVAILABILITY_INDEX,
    DEFAULT_SUBJECT_AVAILABILITY_DIR,
    discover_frank_assets,
    ensure_subject_availability,
    save_availability_index,
)
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.pipeline import crawl_manifest, download_from_manifest, migrate_raw_layout


MESSAGES = {
    "zh": {
        "description": "CIE A-Level 试卷下载命令行工具。",
        "downloaded": "已下载/跳过 {count} 个资源",
        "crawl_counts": "爬取统计: {counts}",
        "saved_assets": "已保存 {asset_count} 个资源，覆盖 {subject_count} 个科目: {path}",
        "discovery_warning": "警告: {count} 个 Frank 列表查询失败；可重新运行补齐可能缺口",
        "sniffed": "已嗅探科目: {subjects}; 失败查询: {failed}",
        "migration": "原始文件布局迁移统计: {counts}",
    },
    "en": {
        "description": "CIE A-Level paper downloader CLI.",
        "downloaded": "downloaded/skipped {count} assets",
        "crawl_counts": "crawl counts: {counts}",
        "saved_assets": "saved {asset_count} assets for {subject_count} subjects: {path}",
        "discovery_warning": "warning: {count} Frank listing queries failed; rerun discovery to fill possible gaps",
        "sniffed": "sniffed subjects: {subjects}; failed queries: {failed}",
        "migration": "raw layout migration counts: {counts}",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cie-alevel-downloader", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言 / Output language.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="从 manifest 下载 CIE PDF。 / Download CIE PDFs from a manifest.")
    download.add_argument("--manifest", type=Path, default=BACKEND_ROOT / "config/exams/cie_a_level_manifest.json")
    download.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    download.add_argument("--limit", type=int)

    crawl = subparsers.add_parser("crawl", help="批量下载并写入 JSONL 状态报告。 / Batch download with a JSONL report.")
    crawl.add_argument("--manifest", type=Path, default=BACKEND_ROOT / "config/exams/cie_a_level_through_2025_manifest.json")
    crawl.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    crawl.add_argument("--report", type=Path, default=BACKEND_ROOT / "data/reports/cie_download_status.jsonl")
    crawl.add_argument("--limit", type=int)
    crawl.add_argument("--delay", type=float, default=3.0)
    crawl.add_argument("--workers", type=int, default=1)
    crawl.add_argument("--no-resume", action="store_true")
    crawl.add_argument("--availability-index", type=Path, default=DEFAULT_AVAILABILITY_INDEX)
    crawl.add_argument("--ignore-availability", action="store_true", help="直接下载 manifest 候选项，不使用 Frank 可用性索引。")

    discover = subparsers.add_parser("discover-frank-assets", help="从 Frank 列表 API 构建可用资源索引。")
    discover.add_argument("--output", type=Path, default=DEFAULT_AVAILABILITY_INDEX)
    discover.add_argument("--qualification", choices=["a_level", "igcse", "all"], default="a_level")
    discover.add_argument("--subject", action="append", dest="subjects", help="科目代码，例如 9709；可重复。")
    discover.add_argument("--start-year", type=int, default=2001)
    discover.add_argument("--end-year", type=int)
    discover.add_argument("--season", action="append", choices=["Mar", "Jun", "Nov"], dest="seasons")
    discover.add_argument("--delay", type=float, default=0.2)
    discover.add_argument("--workers", type=int, default=4)
    discover.add_argument("--timeout", type=float, default=20.0)

    sniff = subparsers.add_parser("sniff-frank-assets", help="为指定科目/年份生成 Frank 可用资源文件。")
    sniff.add_argument("--subject", action="append", dest="subjects", required=True, help="科目代码，例如 9709；可重复。")
    sniff.add_argument("--qualification", choices=["a_level", "igcse", "all"], default="a_level")
    sniff.add_argument("--output-dir", type=Path, default=DEFAULT_SUBJECT_AVAILABILITY_DIR)
    sniff.add_argument("--start-year", type=int, required=True)
    sniff.add_argument("--end-year", type=int, required=True)
    sniff.add_argument("--season", action="append", choices=["Mar", "Jun", "Nov"], dest="seasons")
    sniff.add_argument("--delay", type=float, default=0.2)
    sniff.add_argument("--workers", type=int, default=4)
    sniff.add_argument("--timeout", type=float, default=20.0)
    sniff.add_argument("--force", action="store_true")

    migrate_layout = subparsers.add_parser("migrate-raw-layout", help="迁移旧版原始 PDF 目录布局。")
    migrate_layout.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    message = MESSAGES[args.lang]

    if args.command == "download":
        paths = download_from_manifest(args.manifest, args.raw_root, limit=args.limit)
        print(message["downloaded"].format(count=len(paths)))
    elif args.command == "crawl":
        counts = crawl_manifest(
            args.manifest,
            args.raw_root,
            args.report,
            limit=args.limit,
            delay_seconds=args.delay,
            resume=not args.no_resume,
            max_workers=args.workers,
            availability_index=None if args.ignore_availability else args.availability_index,
        )
        print(message["crawl_counts"].format(counts=counts))
    elif args.command == "discover-frank-assets":
        failures: list[dict[str, object]] = []

        def progress(event: dict[str, object]) -> None:
            if event.get("error"):
                failures.append(event)

        assets = discover_frank_assets(
            qualification=args.qualification,
            subject_codes=set(args.subjects) if args.subjects else None,
            start_year=args.start_year,
            end_year=args.end_year,
            seasons=args.seasons or ("Mar", "Jun", "Nov"),
            delay_seconds=args.delay,
            workers=args.workers,
            timeout_seconds=args.timeout,
            progress=progress,
        )
        save_availability_index(args.output, assets)
        subjects = {asset.subject_code for asset in assets}
        print(message["saved_assets"].format(asset_count=len(assets), subject_count=len(subjects), path=args.output))
        if failures:
            print(message["discovery_warning"].format(count=len(failures)))
    elif args.command == "sniff-frank-assets":
        result = ensure_subject_availability(
            set(args.subjects),
            qualification=args.qualification,
            start_year=args.start_year,
            end_year=args.end_year,
            seasons=args.seasons or ("Mar", "Jun", "Nov"),
            availability_dir=args.output_dir,
            force=args.force,
            delay_seconds=args.delay,
            workers=args.workers,
            timeout_seconds=args.timeout,
        )
        print(message["sniffed"].format(subjects=result["sniffed_subjects"], failed=result["failed_queries"]))
    elif args.command == "migrate-raw-layout":
        counts = migrate_raw_layout(args.raw_root)
        print(message["migration"].format(counts=counts))


if __name__ == "__main__":
    main()


