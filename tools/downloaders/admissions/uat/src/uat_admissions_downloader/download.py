from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Callable, Iterable

from uat_admissions_downloader.models import ArchiveAsset


ProgressCallback = Callable[[dict[str, object]], None]


def download_asset(
    asset: ArchiveAsset,
    raw_root: Path,
    *,
    timeout_seconds: float = 60.0,
) -> tuple[Path, str]:
    target = raw_root / asset.relative_pdf_path
    metadata_path = target.with_suffix(".json")
    if target.exists() and target.stat().st_size > 0 and metadata_path.exists():
        return target, "skipped"
    target.parent.mkdir(parents=True, exist_ok=True)
    part_path = target.with_suffix(".pdf.part")
    request = urllib.request.Request(asset.source_url, headers={"User-Agent": "Oh-My-Exam/0.1"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response, part_path.open("wb") as output:
        while chunk := response.read(128 * 1024):
            output.write(chunk)
    if part_path.stat().st_size == 0:
        part_path.unlink(missing_ok=True)
        raise RuntimeError(f"empty download: {asset.source_url}")
    part_path.replace(target)
    subject_names = {
        "engaa": "Engineering Admissions Assessment",
        "nsaa": "Natural Sciences Admissions Assessment",
        "tmua": "Test of Mathematics for University Admission",
    }
    metadata = {
        "exam_board": "uat",
        "qualification": "admissions",
        "subject_code": asset.exam,
        "subject_name": subject_names[asset.exam],
        "year": asset.year,
        "session": asset.edition,
        "component": asset.component,
        "document_type": asset.document_type,
        "source_stem": asset.stem,
        "source_url": asset.source_url,
        "source_pdf_sha256": _sha256(target),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, "downloaded"


def download_assets(
    assets: Iterable[ArchiveAsset],
    raw_root: Path,
    *,
    delay_seconds: float = 0.2,
    timeout_seconds: float = 60.0,
    progress: ProgressCallback | None = None,
) -> dict[str, int]:
    counts = {"downloaded": 0, "skipped": 0, "failed": 0}
    for asset in assets:
        try:
            path, status = download_asset(asset, raw_root, timeout_seconds=timeout_seconds)
            record: dict[str, object] = {"asset": asset.stem, "status": status, "path": path.as_posix()}
        except Exception as exc:
            status = "failed"
            record = {"asset": asset.stem, "status": status, "message": str(exc)}
        counts[status] += 1
        if progress:
            progress(record)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
    return counts


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
