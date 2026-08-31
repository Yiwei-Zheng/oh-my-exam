from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Iterable

from oh_my_exam.pipelines.adapters.step.downloader.models import EXAM_BOARD, SOURCE_PROVIDER, StepAsset


ProgressCallback = Callable[[dict[str, object]], None]


def download_asset(
    asset: StepAsset,
    raw_root: Path,
    *,
    timeout_seconds: float = 60.0,
    reuse_from: Path | None = None,
    overwrite: bool = False,
) -> tuple[Path, str]:
    target = raw_root / asset.relative_pdf_path
    metadata_path = target.with_suffix(".json")
    if not overwrite and target.exists() and metadata_path.exists() and _pdf_looks_complete(target):
        return target, "skipped"
    if not _pdf_looks_complete(target):
        target.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    part_path = target.with_suffix(".pdf.part")
    if reuse_from is not None and reuse_from.is_file() and _pdf_looks_complete(reuse_from):
        try:
            os.link(reuse_from, target)
        except OSError:
            shutil.copyfile(reuse_from, target)
    else:
        for attempt in range(3):
            request = urllib.request.Request(asset.source_url, headers={"User-Agent": "Oh-My-Exam/0.1"})
            try:
                with urllib.request.urlopen(request, timeout=timeout_seconds) as response, part_path.open("wb") as output:
                    expected_size = response.headers.get("Content-Length")
                    while chunk := response.read(128 * 1024):
                        output.write(chunk)
                if expected_size is not None and part_path.stat().st_size != int(expected_size):
                    raise RuntimeError(f"incomplete download: {asset.source_url}")
                if not _pdf_looks_complete(part_path):
                    raise RuntimeError(f"invalid or truncated PDF: {asset.source_url}")
                part_path.replace(target)
                break
            except Exception:
                part_path.unlink(missing_ok=True)
                if attempt == 2:
                    raise
    metadata = {
        "exam_board": EXAM_BOARD,
        "qualification": "admissions",
        "subject_code": "step",
        "subject_name": "Sixth Term Examination Paper",
        "year": asset.year,
        "session": "archive",
        "component": asset.component,
        "document_type": asset.document_type,
        "source_stem": asset.stem,
        "source_provider": SOURCE_PROVIDER,
        "source_url": asset.source_url,
        "source_pdf_sha256": _sha256(target),
    }
    if asset.contains_papers:
        metadata["contains_papers"] = list(asset.contains_papers)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, "downloaded"


def download_assets(
    assets: Iterable[StepAsset],
    raw_root: Path,
    *,
    delay_seconds: float = 0.2,
    timeout_seconds: float = 60.0,
    progress: ProgressCallback | None = None,
    workers: int = 1,
    overwrite: bool = False,
) -> dict[str, int]:
    assets = list(assets)
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}
    groups: dict[str, list[StepAsset]] = {}
    for asset in assets:
        groups.setdefault(asset.source_url, []).append(asset)

    def run_group(group: list[StepAsset]) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        reuse_from: Path | None = None
        for asset in group:
            try:
                path, status = download_asset(
                    asset,
                    raw_root,
                    timeout_seconds=timeout_seconds,
                    reuse_from=reuse_from,
                    overwrite=overwrite,
                )
                reuse_from = path
                records.append({"asset": asset.stem, "status": status, "path": path.as_posix()})
            except Exception as exc:
                records.append({"asset": asset.stem, "status": "failed", "message": str(exc)})
            if delay_seconds > 0:
                time.sleep(delay_seconds)
        return records

    completed = 0
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as executor:
        futures = [executor.submit(run_group, group) for group in groups.values()]
        for future in as_completed(futures):
            records = future.result()
            for record in records:
                completed += 1
                status = str(record["status"])
                record.update({"index": completed, "total": len(assets)})
                counts[status] += 1
                if progress:
                    progress(record)
    return counts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _pdf_looks_complete(path: Path) -> bool:
    try:
        if path.stat().st_size < 16:
            return False
        with path.open("rb") as source:
            header = source.read(5)
            source.seek(max(0, path.stat().st_size - 4096))
            trailer = source.read()
        return header == b"%PDF-" and b"%%EOF" in trailer
    except OSError:
        return False
