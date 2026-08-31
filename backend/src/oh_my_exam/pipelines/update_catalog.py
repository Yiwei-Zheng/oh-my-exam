from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path

from oh_my_exam.paths import DATA_ROOT
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.frank_discovery import discover_frank_assets
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.pipeline import crawl_assets
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.layout_splitter import split_installed_paper_sets
from oh_my_exam.pipelines.adapters.step.downloader.catalog import discover_assets as discover_step_assets
from oh_my_exam.pipelines.adapters.step.downloader.download import download_assets as download_step_assets
from oh_my_exam.pipelines.adapters.step.splitter.pipeline import split_downloaded as split_step_downloads
from oh_my_exam.pipelines.adapters.uat.downloader.catalog import DEFAULT_ARCHIVE_URLS, discover_assets
from oh_my_exam.pipelines.adapters.uat.downloader.download import download_assets as download_uat_assets
from oh_my_exam.pipelines.adapters.uat.splitter.pipeline import split_downloaded as split_uat_downloads
from oh_my_exam.pipelines.adapters.uat.tmua_pipeline import process_tmua
from oh_my_exam.pipelines.packaging import PackOptions, pack_subject_database
from oh_my_exam.pipelines.release import build_and_activate_release


CIE_NAMES = {"9709": "Mathematics", "9231": "Mathematics - Further"}
UAT_NAMES = {
    "engaa": "Engineering Admissions Assessment",
    "nsaa": "Natural Sciences Admissions Assessment",
}


def _progress(stage: str, progress: int, message: str) -> None:
    print(json.dumps({"stage": stage, "progress": progress, "message": message}, ensure_ascii=False), flush=True)


def update_catalog(data_root: Path, subject_ids: list[str], workers: int) -> Path:
    workers = max(1, min(12, int(workers)))
    raw_root = data_root / "raw_papers"
    processed_root = data_root / "processed_questions"
    report_root = data_root / "reports"
    database_root = data_root / "databases"
    _progress("checking", 5, "正在重新嗅探所选科目的资源")
    failures: list[str] = []
    completed: list[str] = []
    for subject_id in subject_ids:
        try:
            if subject_id.startswith("cie:"):
                code = subject_id.split(":", 1)[1]
                assets = discover_frank_assets(
                    qualification="a_level",
                    subject_codes={code},
                    start_year=2020,
                    end_year=date.today().year,
                    seasons=("Mar", "Jun", "Nov"),
                    workers=workers,
                )
                if not assets:
                    raise RuntimeError("Frank returned no resources")
                _progress("downloading", 18, f"{subject_id}: 发现 {len(assets)} 份 Frank 资源")
                counts = crawl_assets(
                    assets,
                    raw_root,
                    report_root / f"web_update_cie_{code}_download.jsonl",
                    delay_seconds=0.2,
                    max_workers=workers,
                )
                if counts["failed"]:
                    raise RuntimeError(f"download failed for {counts['failed']} assets")
                counts = split_installed_paper_sets(
                    raw_root,
                    processed_root,
                    report_root / f"web_update_cie_{code}_split.jsonl",
                    subject_codes={code},
                    workers=workers,
                )
                if counts["failed"]:
                    raise RuntimeError(f"split failed for {counts['failed']} paper sets")
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
            elif subject_id == "ocr:step":
                assets = discover_step_assets()
                _progress("downloading", 30, f"{subject_id}: 发现 {len(assets)} 份 PMT 资源")
                counts = download_step_assets(assets, raw_root, delay_seconds=0)
                if counts["failed"]:
                    raise RuntimeError(f"download failed for {counts['failed']} assets")
                counts = split_step_downloads(raw_root, processed_root, report_root / "web_update_step_split.jsonl")
                if counts["failed"]:
                    raise RuntimeError(f"split failed for {counts['failed']} assets")
                pack_subject_database(
                    PackOptions(
                        metadata_root=processed_root,
                        output_dir=database_root / "admissions" / "ocr",
                        qualification="admissions",
                        exam_board="ocr",
                        course_code="step",
                        course_display_name="Sixth Term Examination Paper",
                        overwrite=True,
                    )
                )
            elif subject_id == "uat:tmua":
                process_tmua(data_root, download=True, activate=False)
            else:
                exam = subject_id.split(":", 1)[1]
                archive_url = next(url for url in DEFAULT_ARCHIVE_URLS if "esat-preparation" in url)
                assets = [asset for asset in discover_assets(archive_url) if asset.exam == exam]
                if not assets:
                    raise RuntimeError("UAT-UK returned no resources")
                _progress("downloading", 30, f"{subject_id}: 发现 {len(assets)} 份 UAT-UK 资源")
                counts = download_uat_assets(assets, raw_root, delay_seconds=0)
                if counts["failed"]:
                    raise RuntimeError(f"download failed for {counts['failed']} assets")
                counts = split_uat_downloads(
                    raw_root,
                    processed_root,
                    report_root / f"web_update_{exam}_split.jsonl",
                    exams={exam},
                )
                if counts["failed"]:
                    raise RuntimeError(f"split failed for {counts['failed']} assets")
                pack_subject_database(
                    PackOptions(
                        metadata_root=processed_root,
                        output_dir=database_root / "admissions" / "uat",
                        qualification="admissions",
                        exam_board="uat",
                        course_code=exam,
                        course_display_name=UAT_NAMES[exam],
                        overwrite=True,
                    )
                )
            completed.append(subject_id)
        except Exception as exc:
            failures.append(f"{subject_id}: {exc}")
            _progress("splitting", 60, f"{subject_id} 失败，继续处理其他项目: {exc}")

    if not completed:
        raise RuntimeError("all selected projects failed: " + "; ".join(failures))

    _progress("splitting", 68, f"已完成 {len(completed)} 个项目，正在盘点入库")
    active = build_and_activate_release(data_root)
    if failures:
        _progress("classifying", 99, f"已更新 {len(completed)} 个项目；{len(failures)} 个失败: {'; '.join(failures)}")
    else:
        _progress("classifying", 99, "全部所选项目已更新")
    return active


def main() -> None:
    supported = {"cie:9709", "cie:9231", "ocr:step", "uat:engaa", "uat:nsaa", "uat:tmua"}
    selected = [item for item in os.environ.get("OME_UPDATE_SUBJECTS", ",".join(sorted(supported))).split(",") if item]
    unknown = set(selected) - supported
    if unknown:
        raise ValueError(f"unsupported update subjects: {', '.join(sorted(unknown))}")
    update_catalog(DATA_ROOT, selected, int(os.environ.get("OME_UPDATE_CONCURRENCY", "4")))


if __name__ == "__main__":
    main()
