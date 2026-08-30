from __future__ import annotations

import argparse
import json
from pathlib import Path

from oh_my_exam.paths import DATA_ROOT
from oh_my_exam.pipelines.adapters.uat.downloader.catalog import DEFAULT_ARCHIVE_URLS, discover_assets
from oh_my_exam.pipelines.adapters.uat.downloader.download import download_assets
from oh_my_exam.pipelines.adapters.uat.splitter.cutter import SplitOptions
from oh_my_exam.pipelines.adapters.uat.splitter.pipeline import split_downloaded
from oh_my_exam.pipelines.packaging import PackOptions, pack_subject_database
from oh_my_exam.pipelines.release import build_and_activate_release


def process_tmua(
    data_root: Path,
    *,
    download: bool = True,
    activate: bool = True,
    start_year: int | None = None,
    end_year: int | None = None,
    dpi: int = 180,
    quality: int = 90,
) -> Path:
    """Download, split, pair, package, classify, and publish the TMUA archive."""
    raw_root = data_root / "raw_papers"
    processed_root = data_root / "processed_questions"
    report_root = data_root / "reports"
    database_root = data_root / "databases"

    if download:
        archive_url = next(url for url in DEFAULT_ARCHIVE_URLS if "tmua-preparation" in url)
        assets = [asset for asset in discover_assets(archive_url) if asset.exam == "tmua"]
        assets = [
            asset for asset in assets
            if (asset.year is None or start_year is None or asset.year >= start_year)
            and (asset.year is None or end_year is None or asset.year <= end_year)
        ]
        report_root.mkdir(parents=True, exist_ok=True)
        with (report_root / "tmua_download.jsonl").open("a", encoding="utf-8") as report:
            counts = download_assets(
                assets,
                raw_root,
                progress=lambda item: report.write(json.dumps(item, ensure_ascii=False) + "\n"),
            )
        if counts["failed"]:
            raise RuntimeError(f"TMUA download failed for {counts['failed']} assets")

    split_counts = split_downloaded(
        raw_root,
        processed_root,
        report_root / "tmua_split.jsonl",
        exams={"tmua"},
        start_year=start_year,
        end_year=end_year,
        options=SplitOptions(dpi=dpi, quality=quality),
    )
    if split_counts["failed"] or split_counts["split"] == 0:
        raise RuntimeError(f"TMUA split did not complete cleanly: {split_counts}")

    portable_dir = database_root / "admissions" / "uat"
    summary = pack_subject_database(PackOptions(
        metadata_root=processed_root,
        output_dir=portable_dir,
        qualification="admissions",
        exam_board="uat",
        course_code="tmua",
        course_display_name="Test of Mathematics for University Admission",
        overwrite=True,
    ))
    if summary.matched_pairs == 0 or any((summary.only_qp, summary.only_ms, summary.duplicate_qp, summary.duplicate_ms, summary.ambiguous_match)):
        raise RuntimeError("TMUA question/answer pairing validation failed: " + ", ".join(summary.as_lines()))

    if activate:
        return build_and_activate_release(data_root)
    if summary.database_path is None:
        raise RuntimeError("TMUA packer did not return a database path")
    return summary.database_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reproducible TMUA ingestion: download, split, pair, package, classify, and publish.",
    )
    parser.add_argument("--data-root", type=Path, default=DATA_ROOT)
    parser.add_argument("--skip-download", action="store_true", help="Use the official PDFs already under data/raw_papers.")
    parser.add_argument("--skip-activate", action="store_true", help="Build only the portable TMUA database.")
    parser.add_argument("--start-year", type=int)
    parser.add_argument("--end-year", type=int)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--quality", type=int, default=90)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    result = process_tmua(
        args.data_root.resolve(),
        download=not args.skip_download,
        activate=not args.skip_activate,
        start_year=args.start_year,
        end_year=args.end_year,
        dpi=args.dpi,
        quality=args.quality,
    )
    print(f"database_path={result}")


if __name__ == "__main__":
    main()
