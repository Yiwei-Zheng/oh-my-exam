from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import asdict
import json
import re
from pathlib import Path

from oh_my_exam.pipelines.adaptive_rate import AdaptiveRateLimiter
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.cie import load_assets
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.download import DownloadOutcome, download_asset, try_download_asset
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.frank_discovery import load_availability_index
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.models import PaperAsset
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.subject_names import english_subject_name


def download_from_manifest(manifest_path: Path, output_root: Path, *, limit: int | None = None) -> list[Path]:
    assets = load_assets(manifest_path)
    if limit is not None:
        assets = assets[:limit]
    return [download_asset(asset, output_root) for asset in assets]


def crawl_manifest(
    manifest_path: Path,
    output_root: Path,
    report_path: Path,
    *,
    limit: int | None = None,
    delay_seconds: float = 2.0,
    resume: bool = True,
    max_workers: int = 1,
    availability_index: Path | None = None,
) -> dict[str, int]:
    assets = load_availability_index(availability_index) if availability_index and availability_index.exists() else load_assets(manifest_path)
    if limit is not None:
        assets = assets[:limit]
    return crawl_assets(assets, output_root, report_path, delay_seconds=delay_seconds, resume=resume, max_workers=max_workers)


def crawl_assets(
    assets: list[PaperAsset],
    output_root: Path,
    report_path: Path,
    *,
    delay_seconds: float = 2.0,
    resume: bool = True,
    max_workers: int = 1,
    progress: Callable[[dict[str, object]], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
    skipped_progress_interval: int = 1,
    overwrite: bool = False,
    limiter: AdaptiveRateLimiter | None = None,
) -> dict[str, int]:
    completed = _read_completed_stems(report_path) if resume else set()
    counts = {"downloaded": 0, "missing": 0, "failed": 0, "rate_limited": 0, "skipped": 0}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    max_workers = max(1, int(max_workers))
    limiter = limiter or AdaptiveRateLimiter(
        max_workers,
        initial_interval_seconds=delay_seconds,
    )
    with report_path.open("a", encoding="utf-8") as report:
        pending: list[tuple[int, PaperAsset]] = []
        for index, asset in enumerate(assets, start=1):
            if asset.stem in completed:
                counts["skipped"] += 1
                if progress and _should_emit_skipped_progress(index, len(assets), counts, skipped_progress_interval):
                    progress({"index": index, "total": len(assets), "asset": asset.stem, "status": "skipped", "counts": dict(counts)})
                continue
            pending.append((index, asset))

        if max_workers == 1:
            for index, asset in pending:
                if should_stop and should_stop():
                    break
                options: dict[str, object] = {
                    "min_delay_seconds": delay_seconds,
                    "limiter": limiter,
                }
                if overwrite:
                    options["overwrite"] = True
                outcome = try_download_asset(asset, output_root, **options)
                _write_crawl_outcome(report, outcome)
                counts[outcome.status] += 1
                if progress:
                    progress({"index": index, "total": len(assets), "asset": asset.stem, "status": outcome.status, "counts": dict(counts), "message": outcome.message})
                if should_stop and should_stop():
                    break
            return counts

        asset_iter = iter(pending)
        future_assets: dict[Future[DownloadOutcome], tuple[int, PaperAsset]] = {}

        def submit_next(executor: ThreadPoolExecutor) -> bool:
            if should_stop and should_stop():
                return False
            try:
                index, asset = next(asset_iter)
            except StopIteration:
                return False
            options: dict[str, object] = {
                "min_delay_seconds": delay_seconds,
                "limiter": limiter,
            }
            if overwrite:
                options["overwrite"] = True
            future = executor.submit(try_download_asset, asset, output_root, **options)
            future_assets[future] = (index, asset)
            return True

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for _ in range(max_workers):
                if not submit_next(executor):
                    break
            while future_assets:
                done, _ = wait(future_assets, return_when=FIRST_COMPLETED)
                for future in done:
                    index, _asset = future_assets.pop(future)
                    if future.cancelled():
                        continue
                    outcome = future.result()
                    _write_crawl_outcome(report, outcome)
                    counts[outcome.status] += 1
                    if progress:
                        progress({"index": index, "total": len(assets), "asset": outcome.asset.stem, "status": outcome.status, "counts": dict(counts), "message": outcome.message})
                    if should_stop and should_stop():
                        for pending_future in future_assets:
                            pending_future.cancel()
                        future_assets.clear()
                        break
                    submit_next(executor)
    return counts


def filter_assets(
    assets: list[PaperAsset],
    *,
    subject_codes: set[str] | None = None,
    document_types: set[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[PaperAsset]:
    filtered: list[PaperAsset] = []
    for asset in assets:
        if subject_codes and asset.subject_code not in subject_codes:
            continue
        if document_types and asset.document_type not in document_types:
            continue
        year = 2000 + int(asset.session[1:3])
        if start_year is not None and year < start_year:
            continue
        if end_year is not None and year > end_year:
            continue
        filtered.append(asset)
    return filtered


def migrate_raw_layout(raw_root: Path) -> dict[str, int]:
    counts = {"migrated": 0, "migrated_part": 0, "already_current": 0, "missing_pdf": 0, "failed": 0}
    for metadata_path in sorted(raw_root.rglob("*.json")):
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
            asset = PaperAsset(
                exam_board=raw["exam_board"],
                qualification=raw["qualification"],
                subject_code=raw["subject_code"],
                subject_name=english_subject_name(raw["exam_board"], raw["qualification"], raw["subject_code"], raw["subject_name"]),
                session=raw["session"],
                document_type=raw["document_type"],
                component=raw["component"],
            )
            current_pdf = metadata_path.with_suffix(".pdf")
            if not current_pdf.exists():
                counts["missing_pdf"] += 1
                continue
            target_pdf = raw_root / asset.relative_pdf_path
            target_metadata = target_pdf.with_suffix(".json")
            if current_pdf == target_pdf and metadata_path == target_metadata:
                counts["already_current"] += 1
                continue
            target_pdf.parent.mkdir(parents=True, exist_ok=True)
            current_pdf.replace(target_pdf)
            metadata_path.replace(target_metadata)
            counts["migrated"] += 1
        except Exception:
            counts["failed"] += 1
    counts["migrated_part"] = _migrate_legacy_part_files(raw_root)
    return counts


def _should_emit_skipped_progress(index: int, total: int, counts: dict[str, int], skipped_progress_interval: int) -> bool:
    interval = max(1, int(skipped_progress_interval))
    skipped = counts.get("skipped", 0)
    return interval == 1 or skipped % interval == 0 or index == total


def _write_crawl_outcome(report, outcome: DownloadOutcome) -> None:
    report.write(json.dumps(_outcome_record(outcome), ensure_ascii=False) + "\n")
    report.flush()


def _migrate_legacy_part_files(raw_root: Path) -> int:
    migrated = 0
    pattern = re.compile(r"^(?P<code>\d{4})_(?P<session>[msw]\d{2})_(?P<document_type>[a-z]+)_(?P<component>.+)\.pdf\.part$")
    for part_path in sorted(raw_root.rglob("*.pdf.part")):
        match = pattern.match(part_path.name)
        if not match:
            continue
        session = match.group("session")
        code = match.group("code")
        parent = part_path.parent
        if parent.name != session or parent.parent.name != code:
            continue
        year = 2000 + int(session[1:3])
        target = parent.parent / str(year) / session / part_path.name
        if part_path == target or target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        part_path.replace(target)
        migrated += 1
    return migrated


def _read_completed_stems(report_path: Path) -> set[str]:
    if not report_path.exists():
        return set()
    completed: set[str] = set()
    with report_path.open("r", encoding="utf-8") as report:
        for line in report:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("status") in {"downloaded", "missing"} and isinstance(record.get("stem"), str):
                completed.add(record["stem"])
    return completed


def _outcome_record(outcome: DownloadOutcome) -> dict[str, object]:
    record = asdict(outcome.asset)
    record.update({"stem": outcome.asset.stem, "status": outcome.status, "path": str(outcome.path) if outcome.path else None, "message": outcome.message})
    return record
