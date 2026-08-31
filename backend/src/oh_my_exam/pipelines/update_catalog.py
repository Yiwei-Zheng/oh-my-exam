from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path

from oh_my_exam.paths import DATA_ROOT
from oh_my_exam.pipelines.adaptive_rate import AdaptiveRateLimiter
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.frank_discovery import discover_frank_assets
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.pipeline import crawl_assets
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.layout_splitter import split_installed_paper_sets
from oh_my_exam.pipelines.adapters.step.downloader.catalog import discover_assets as discover_step_assets
from oh_my_exam.pipelines.adapters.step.downloader.download import download_assets as download_step_assets
from oh_my_exam.pipelines.adapters.step.splitter.pipeline import split_downloaded as split_step_downloads
from oh_my_exam.pipelines.adapters.uat.downloader.catalog import DEFAULT_ARCHIVE_URLS, discover_assets
from oh_my_exam.pipelines.adapters.uat.downloader.download import download_assets as download_uat_assets
from oh_my_exam.pipelines.adapters.uat.splitter.pipeline import split_downloaded as split_uat_downloads
from oh_my_exam.pipelines.packaging import PackOptions, pack_subject_database
from oh_my_exam.pipelines.release import build_and_activate_release


CIE_NAMES = {"9709": "Mathematics", "9231": "Mathematics - Further"}
UAT_NAMES = {
    "engaa": "Engineering Admissions Assessment",
    "nsaa": "Natural Sciences Admissions Assessment",
    "tmua": "Test of Mathematics for University Admission",
}
STAGES = ("download", "split", "inventory", "search")


def _progress(stage: str, progress: int, message: str) -> None:
    print(json.dumps({"stage": stage, "progress": progress, "message": message}, ensure_ascii=False), flush=True)


def update_catalog(
    data_root: Path,
    subject_ids: list[str],
    workers: int,
    stage: str = "all",
    mode: str = "update",
) -> Path:
    workers = max(1, min(32, int(workers)))
    if stage not in {"all", *STAGES}:
        raise ValueError(f"unsupported update stage: {stage}")
    if mode not in {"update", "overwrite"}:
        raise ValueError(f"unsupported update mode: {mode}")
    raw_root = data_root / "raw_papers"
    processed_root = data_root / "processed_questions"
    report_root = data_root / "reports"
    database_root = data_root / "databases"
    overwrite = mode == "overwrite"
    failures: list[str] = []
    stages = STAGES if stage == "all" else (stage,)
    active = data_root
    if stage == "all":
        _progress("checking", 5, "正在检查来源并准备完整流水线")
    for current_stage in stages:
        if current_stage == "search":
            _progress("classifying", 82, "正在建立搜索索引并发布题库")
            active = build_and_activate_release(data_root)
            continue
        completed = 0
        for subject_index, subject_id in enumerate(subject_ids):
            try:
                _run_subject_stage(
                    current_stage,
                    subject_id,
                    raw_root,
                    processed_root,
                    report_root,
                    database_root,
                    workers,
                    overwrite,
                    subject_index,
                    len(subject_ids),
                )
                completed += 1
            except Exception as exc:
                failures.append(f"{current_stage}/{subject_id}: {exc}")
                _progress(_stage_name(current_stage), 60, f"{subject_id} 失败，继续处理其他项目: {exc}")
        if not completed:
            raise RuntimeError(f"all selected projects failed during {current_stage}: " + "; ".join(failures))
    if failures:
        _progress("classifying", 99, f"已更新 {completed} 个项目；{len(failures)} 个失败: {'; '.join(failures)}")
    else:
        _progress(_stage_name(stages[-1]), 99, "所选操作已完成")
    return active


def _run_subject_stage(
    stage: str,
    subject_id: str,
    raw_root: Path,
    processed_root: Path,
    report_root: Path,
    database_root: Path,
    workers: int,
    overwrite: bool,
    subject_index: int,
    subject_count: int,
) -> None:
    stage_ranges = {"download": (8, 40), "split": (40, 68), "inventory": (68, 82)}
    lower, upper = stage_ranges[stage]

    def emit(fraction: float, message: str) -> None:
        overall = (subject_index + max(0.0, min(1.0, fraction))) / subject_count
        _progress(_stage_name(stage), round(lower + (upper - lower) * overall), message)

    def admission_progress(record: dict[str, object], operation: str) -> None:
        completed = int(record.get("index") or 0)
        total = max(1, int(record.get("total") or 1))
        emit(completed / total, f"{subject_id}: {operation} {record.get('asset', '')} ({completed}/{total})")

    if subject_id.startswith("cie:"):
        code = subject_id.split(":", 1)[1]
        if stage == "download":
            emit(0, f"{subject_id}: 正在发现可下载资源")
            limiter = AdaptiveRateLimiter(
                workers,
                initial_interval_seconds=0.2,
            )
            assets = discover_frank_assets(
                qualification="a_level",
                subject_codes={code},
                start_year=2020,
                end_year=date.today().year,
                seasons=("Mar", "Jun", "Nov"),
                workers=workers,
                limiter=limiter,
            )
            if not assets:
                raise RuntimeError("Frank returned no resources")
            emit(0, f"{subject_id}: 发现 {len(assets)} 份 Frank 资源")

            def download_progress(record: dict[str, object]) -> None:
                counts = record.get("counts") or {}
                completed = sum(int(value) for value in counts.values()) if isinstance(counts, dict) else 0
                total = max(1, int(record.get("total") or len(assets)))
                emit(completed / total, f"{subject_id}: 正在下载 {record.get('asset', '')} ({completed}/{total})")

            counts = crawl_assets(
                assets,
                raw_root,
                report_root / f"web_update_cie_{code}_download.jsonl",
                delay_seconds=0.2,
                resume=False,
                max_workers=workers,
                progress=download_progress,
                overwrite=overwrite,
                limiter=limiter,
            )
        elif stage == "split":
            emit(0, f"{subject_id}: 正在准备题目和答案切图")

            def split_progress(record: dict[str, object]) -> None:
                completed = int(record.get("index") or 0)
                total = max(1, int(record.get("total") or 1))
                emit(completed / total, f"{subject_id}: 正在切分 {record.get('key', '')} ({completed}/{total})")

            counts = split_installed_paper_sets(
                raw_root,
                processed_root,
                report_root / f"web_update_cie_{code}_split.jsonl",
                subject_codes={code},
                workers=workers,
                progress=split_progress,
                overwrite=overwrite,
            )
        else:
            emit(0, f"{subject_id}: 正在盘点入库")
            pack_subject_database(PackOptions(
                metadata_root=processed_root,
                output_dir=database_root / "a_level" / "cie",
                qualification="a_level",
                exam_board="cie",
                course_code=code,
                course_display_name=CIE_NAMES[code],
                overwrite=overwrite,
            ))
            emit(1, f"{subject_id}: 已完成盘点入库")
            return
    elif subject_id == "ocr:step":
        if stage == "download":
            assets = discover_step_assets()
            emit(0, f"{subject_id}: 发现 {len(assets)} 份 PMT 资源，正在下载")
            counts = download_step_assets(
                assets,
                raw_root,
                delay_seconds=0,
                workers=workers,
                progress=lambda record: admission_progress(record, "正在下载"),
                overwrite=overwrite,
            )
        elif stage == "split":
            emit(0, f"{subject_id}: 正在切分题目和答案图片")
            counts = split_step_downloads(
                raw_root,
                processed_root,
                report_root / "web_update_step_split.jsonl",
                progress=lambda record: admission_progress(record, "正在切分"),
                overwrite=overwrite,
            )
        else:
            emit(0, f"{subject_id}: 正在盘点入库")
            pack_subject_database(PackOptions(
                metadata_root=processed_root,
                output_dir=database_root / "admissions" / "ocr",
                qualification="admissions",
                exam_board="ocr",
                course_code="step",
                course_display_name="Sixth Term Examination Paper",
                overwrite=overwrite,
            ))
            emit(1, f"{subject_id}: 已完成盘点入库")
            return
    else:
        exam = subject_id.split(":", 1)[1]
        if stage == "download":
            page = "tmua-preparation" if exam == "tmua" else "esat-preparation"
            archive_url = next(url for url in DEFAULT_ARCHIVE_URLS if page in url)
            assets = [asset for asset in discover_assets(archive_url) if asset.exam == exam]
            if not assets:
                raise RuntimeError("UAT-UK returned no resources")
            emit(0, f"{subject_id}: 发现 {len(assets)} 份 UAT-UK 资源，正在下载")
            counts = download_uat_assets(
                assets,
                raw_root,
                delay_seconds=0,
                workers=workers,
                progress=lambda record: admission_progress(record, "正在下载"),
                overwrite=overwrite,
            )
        elif stage == "split":
            emit(0, f"{subject_id}: 正在切分题目和答案图片")
            counts = split_uat_downloads(
                raw_root,
                processed_root,
                report_root / f"web_update_{exam}_split.jsonl",
                exams={exam},
                progress=lambda record: admission_progress(record, "正在切分"),
                overwrite=overwrite,
            )
        else:
            emit(0, f"{subject_id}: 正在盘点入库")
            pack_subject_database(PackOptions(
                metadata_root=processed_root,
                output_dir=database_root / "admissions" / "uat",
                qualification="admissions",
                exam_board="uat",
                course_code=exam,
                course_display_name=UAT_NAMES[exam],
                overwrite=overwrite,
            ))
            emit(1, f"{subject_id}: 已完成盘点入库")
            return
    if counts["failed"]:
        raise RuntimeError(f"{stage} failed for {counts['failed']} assets")


def _stage_name(stage: str) -> str:
    return {
        "download": "downloading",
        "split": "splitting",
        "inventory": "cataloging",
        "search": "classifying",
    }[stage]


def main() -> None:
    supported = {"cie:9709", "cie:9231", "ocr:step", "uat:engaa", "uat:nsaa", "uat:tmua"}
    selected = [item for item in os.environ.get("OME_UPDATE_SUBJECTS", ",".join(sorted(supported))).split(",") if item]
    unknown = set(selected) - supported
    if unknown:
        raise ValueError(f"unsupported update subjects: {', '.join(sorted(unknown))}")
    update_catalog(
        DATA_ROOT,
        selected,
        int(os.environ.get("OME_UPDATE_CONCURRENCY", "4")),
        os.environ.get("OME_UPDATE_STAGE", "all"),
        os.environ.get("OME_UPDATE_MODE", "update"),
    )


if __name__ == "__main__":
    main()
