from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import json
import os
from pathlib import Path

from oh_my_exam.paths import DATA_ROOT
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.frank_discovery import discover_frank_assets
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.pipeline import crawl_assets
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.layout_splitter import split_installed_paper_sets
from oh_my_exam.pipelines.adapters.uat.downloader.catalog import DEFAULT_ARCHIVE_URLS, discover_assets
from oh_my_exam.pipelines.adapters.uat.downloader.download import download_asset as download_uat_asset
from oh_my_exam.pipelines.adapters.uat.tmua_pipeline import process_tmua
from oh_my_exam.pipelines.packaging import PackOptions, pack_subject_database
from oh_my_exam.pipelines.release import build_and_activate_release


CIE_NAMES = {"9709": "Mathematics", "9231": "Mathematics - Further"}


def _progress(stage: str, progress: int, message: str) -> None:
    print(json.dumps({"stage": stage, "progress": progress, "message": message}, ensure_ascii=False), flush=True)


def update_catalog(data_root: Path, subject_ids: list[str], workers: int) -> Path:
    workers = max(1, min(12, int(workers)))
    raw_root = data_root / "raw_papers"
    processed_root = data_root / "processed_questions"
    report_root = data_root / "reports"
    database_root = data_root / "databases"
    cie_codes = {item.split(":", 1)[1] for item in subject_ids if item.startswith("cie:")}

    _progress("checking", 5, "正在重新嗅探所选科目的资源")
    if cie_codes:
        assets = discover_frank_assets(
            qualification="a_level",
            subject_codes=cie_codes,
            start_year=2020,
            end_year=date.today().year,
            seasons=("Mar", "Jun", "Nov"),
            workers=workers,
        )
        _progress("downloading", 18, f"发现 {len(assets)} 份 CIE 资源，开始并发下载")
        counts = crawl_assets(
            assets,
            raw_root,
            report_root / "web_update_cie_download.jsonl",
            delay_seconds=0.2,
            max_workers=workers,
        )
        if counts["failed"]:
            raise RuntimeError(f"CIE download failed for {counts['failed']} assets")

    if "uat:tmua" in subject_ids:
        archive_url = next(url for url in DEFAULT_ARCHIVE_URLS if "tmua-preparation" in url)
        assets = [asset for asset in discover_assets(archive_url) if asset.exam == "tmua"]
        _progress("downloading", 30, f"发现 {len(assets)} 份 TMUA 资源，开始并发下载")
        report_root.mkdir(parents=True, exist_ok=True)
        failures: list[str] = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(download_uat_asset, asset, raw_root): asset for asset in assets}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    failures.append(str(exc))
        if failures:
            raise RuntimeError(f"TMUA download failed for {len(failures)} assets: {failures[0]}")

    _progress("splitting", 48, "下载完成，正在进入切题工作流")
    if cie_codes:
        counts = split_installed_paper_sets(
            raw_root,
            processed_root,
            report_root / "web_update_cie_split.jsonl",
            subject_codes=cie_codes,
            workers=workers,
        )
        if counts["failed"]:
            raise RuntimeError(f"CIE split failed for {counts['failed']} paper sets")
        for code in sorted(cie_codes):
            pack_subject_database(
                PackOptions(
                    metadata_root=processed_root,
                    output_dir=database_root / "a_level" / "cie",
                    qualification="a_level",
                    exam_board="cie",
                    course_code=code,
                    course_display_name=CIE_NAMES[code],
                    overwrite=True,
                )
            )

    if "uat:tmua" in subject_ids:
        process_tmua(data_root, download=False, activate=False)

    _progress("cataloging", 76, "切题完成，正在盘点并写入候选题库")
    active = build_and_activate_release(data_root)
    _progress("classifying", 99, "题目已入库并建立搜索索引")
    return active


def main() -> None:
    selected = [item for item in os.environ.get("OME_UPDATE_SUBJECTS", "cie:9709,cie:9231,uat:tmua").split(",") if item]
    unknown = set(selected) - {"cie:9709", "cie:9231", "uat:tmua"}
    if unknown:
        raise ValueError(f"unsupported update subjects: {', '.join(sorted(unknown))}")
    update_catalog(DATA_ROOT, selected, int(os.environ.get("OME_UPDATE_CONCURRENCY", "4")))


if __name__ == "__main__":
    main()
