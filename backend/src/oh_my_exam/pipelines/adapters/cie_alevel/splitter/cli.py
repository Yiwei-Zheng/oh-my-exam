from __future__ import annotations

import argparse
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Sequence

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.cie import load_assets
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.content_backfill import backfill_processed_question_content
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.pipeline import ingest_slices, split_asset_pdf
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.layout_splitter import SplitOptions, split_installed_paper_sets
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.database import connect


MESSAGES = {
    "zh": {
        "description": "CIE A-Level 本地切题命令行工具；已支持 9709/9231 几何小问切题。",
        "ready_db": "数据库已就绪: {path}",
        "created": "已为 {stem} 创建 {count} 个切片",
        "split_counts": "切题统计: {counts}",
        "ingested": "已为 {stem} 入库 {count} 道题",
        "backfilled_content": "题目卷内容字段回填统计: {counts}",
    },
    "en": {
        "description": "CIE A-Level local splitter CLI with 9709/9231 geometry subquestion cutters.",
        "ready_db": "database ready: {path}",
        "created": "created {count} slices for {stem}",
        "split_counts": "split counts: {counts}",
        "ingested": "ingested {count} questions for {stem}",
        "backfilled_content": "question-paper content backfill counts: {counts}",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cie-alevel-splitter", description=MESSAGES["zh"]["description"])
    parser.add_argument("--lang", choices=["zh", "en"], default="zh", help="输出语言 / Output language.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="创建或迁移本地 SQLite 数据库。 / Create or migrate SQLite.")
    init_db.add_argument("--db", type=Path, default=BACKEND_ROOT / "data/exam_bank.sqlite3")

    split = subparsers.add_parser("split", help="切分 manifest 中的单个资源。 / Split one manifest asset.")
    split.add_argument("--manifest", type=Path, default=BACKEND_ROOT / "config/exams/cie_a_level_manifest.json")
    split.add_argument("--asset-index", type=int, default=0)
    split.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    split.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")

    split_all = subparsers.add_parser("split-downloaded", help="切分已下载且带 metadata 的 PDF。 / Split downloaded PDFs with metadata.")
    split_all.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    split_all.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")
    split_all.add_argument("--report", type=Path, default=BACKEND_ROOT / "data/reports/cie_split_status.jsonl")
    split_all.add_argument("--limit", type=int)
    split_all.add_argument("--subject", action="append", dest="subjects", help="科目代码，例如 9709 或 9231；可重复。")
    split_all.add_argument("--start-year", type=int)
    split_all.add_argument("--end-year", type=int)
    split_all.add_argument("--paper-key", action="append", dest="paper_keys", help="GUI/listing 中的本地试卷 key；可重复。")
    split_all.add_argument("--workers", type=int, default=1)
    split_all.add_argument("--dpi", type=int, default=150)
    split_all.add_argument("--threshold", type=int, default=215)
    split_all.add_argument("--quality", type=int, default=88)
    split_all.add_argument("--keep-answer-lines", action="store_true")

    ingest = subparsers.add_parser("ingest", help="切分并写入 SQLite。 / Split and ingest one QP/MS asset pair.")
    ingest.add_argument("--manifest", type=Path, default=BACKEND_ROOT / "config/exams/cie_a_level_manifest.json")
    ingest.add_argument("--asset-index", type=int, default=0)
    ingest.add_argument("--raw-root", type=Path, default=BACKEND_ROOT / "data/raw_papers")
    ingest.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")
    ingest.add_argument("--db", type=Path, default=BACKEND_ROOT / "data/exam_bank.sqlite3")

    backfill_content = subparsers.add_parser(
        "backfill-content",
        help="为已有题目卷 JSON 回填 content 字段，并清理 MS content 字段。 / Backfill QP content and clear MS content fields.",
    )
    backfill_content.add_argument("--processed-root", type=Path, default=BACKEND_ROOT / "data/processed_questions")
    backfill_content.add_argument("--limit", type=int)
    backfill_content.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    message = MESSAGES[args.lang]

    if args.command == "init-db":
        with connect(args.db):
            pass
        print(message["ready_db"].format(path=args.db))
    elif args.command == "split":
        asset = load_assets(args.manifest)[args.asset_index]
        slices = split_asset_pdf(asset, args.raw_root, args.processed_root)
        print(message["created"].format(count=len(slices), stem=asset.stem))
    elif args.command == "split-downloaded":
        counts = split_installed_paper_sets(
            args.raw_root,
            args.processed_root,
            args.report,
            keys=set(args.paper_keys) if args.paper_keys else None,
            subject_codes=set(args.subjects) if args.subjects else None,
            start_year=args.start_year,
            end_year=args.end_year,
            limit=args.limit,
            workers=args.workers,
            options=SplitOptions(
                dpi=args.dpi,
                threshold=args.threshold,
                quality=args.quality,
                remove_answer_lines=not args.keep_answer_lines,
            ),
        )
        print(message["split_counts"].format(counts=counts))
    elif args.command == "ingest":
        assets = load_assets(args.manifest)
        question_asset = assets[args.asset_index]
        mark_asset = next(
            (
                asset
                for asset in assets
                if asset.subject_code == question_asset.subject_code
                and asset.session == question_asset.session
                and asset.component == question_asset.component
                and asset.document_type == "ms"
            ),
            None,
        )
        question_slices = split_asset_pdf(question_asset, args.raw_root, args.processed_root)
        mark_slices = split_asset_pdf(mark_asset, args.raw_root, args.processed_root) if mark_asset else []
        ingest_slices(args.db, question_asset, args.raw_root, question_slices, mark_slices)
        print(message["ingested"].format(count=len(question_slices), stem=question_asset.stem))
    elif args.command == "backfill-content":
        counts = backfill_processed_question_content(args.processed_root, limit=args.limit, overwrite=args.overwrite)
        print(message["backfilled_content"].format(counts=counts))


if __name__ == "__main__":
    main()


