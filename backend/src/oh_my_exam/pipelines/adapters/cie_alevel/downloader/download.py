from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path

from oh_my_exam.pipelines.adapters.cie_alevel.downloader.models import PaperAsset
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.cie import build_frank_cie_url
from oh_my_exam.pipelines.adapters.cie_alevel.downloader.subject_names import english_subject_name


class DownloadError(RuntimeError):
    pass


class RateLimitedError(DownloadError):
    pass


@dataclass(frozen=True)
class DownloadOutcome:
    asset: PaperAsset
    status: str
    path: Path | None
    message: str


def download_asset(
    asset: PaperAsset,
    output_root: Path,
    *,
    min_delay_seconds: float = 2.0,
    timeout_seconds: float = 45.0,
) -> Path:
    target = output_root / asset.relative_pdf_path
    target.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = target.with_suffix(".json")
    _migrate_legacy_asset_files(asset, output_root, target)
    if target.exists() and target.stat().st_size > 0 and metadata_path.exists():
        return target

    legacy_part_path = target.with_suffix(target.suffix + ".part")
    if legacy_part_path.exists() and not target.exists():
        shutil.copyfile(legacy_part_path, target)

    downloaded = target.stat().st_size if target.exists() else 0
    request = urllib.request.Request(build_frank_cie_url(asset), headers={"User-Agent": "Oh-My-Exam/0.1"})
    if downloaded:
        request.add_header("Range", f"bytes={downloaded}-")

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            mode = "ab" if downloaded and response.status == 206 else "wb"
            with target.open(mode) as fh:
                while True:
                    chunk = response.read(1024 * 128)
                    if not chunk:
                        break
                    fh.write(chunk)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RateLimitedError(f"rate limited for {asset.stem}: HTTP 429") from exc
        if exc.code == 404:
            raise DownloadError(f"not found: {asset.stem}") from exc
        raise DownloadError(f"download failed for {asset.stem}: HTTP {exc.code}") from exc
    except OSError as exc:
        raise DownloadError(f"download failed for {asset.stem}: {exc}") from exc

    write_download_metadata(target, asset)
    time.sleep(min_delay_seconds)
    return target


def _migrate_legacy_asset_files(asset: PaperAsset, output_root: Path, target: Path) -> None:
    legacy_pdf = output_root / asset.legacy_relative_pdf_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if legacy_pdf != target and not target.exists() and legacy_pdf.exists():
        legacy_pdf.replace(target)
        legacy_metadata = legacy_pdf.with_suffix(".json")
        if legacy_metadata.exists():
            legacy_metadata.replace(target.with_suffix(".json"))

    legacy_part = legacy_pdf.with_suffix(legacy_pdf.suffix + ".part")
    target_part = target.with_suffix(target.suffix + ".part")
    if legacy_part != target_part and not target_part.exists() and legacy_part.exists():
        legacy_part.replace(target_part)


def try_download_asset(
    asset: PaperAsset,
    output_root: Path,
    *,
    min_delay_seconds: float = 2.0,
    timeout_seconds: float = 45.0,
    rate_limit_retries: int = 5,
    rate_limit_wait_seconds: float | None = None,
) -> DownloadOutcome:
    rate_limit_attempts = 0
    try:
        while True:
            try:
                path = download_asset(
                    asset,
                    output_root,
                    min_delay_seconds=min_delay_seconds,
                    timeout_seconds=timeout_seconds,
                )
                return DownloadOutcome(asset=asset, status="downloaded", path=path, message="")
            except RateLimitedError as exc:
                rate_limit_attempts += 1
                if rate_limit_attempts > rate_limit_retries:
                    return DownloadOutcome(asset=asset, status="rate_limited", path=None, message=str(exc))
                time.sleep(rate_limit_wait_seconds if rate_limit_wait_seconds is not None else max(min_delay_seconds * 8, 30.0))
    except RateLimitedError as exc:
        time.sleep(min_delay_seconds * 4)
        return DownloadOutcome(asset=asset, status="rate_limited", path=None, message=str(exc))
    except DownloadError as exc:
        status = "missing" if str(exc).startswith("not found:") else "failed"
        if status == "missing":
            time.sleep(min_delay_seconds)
        return DownloadOutcome(asset=asset, status=status, path=None, message=str(exc))


def write_download_metadata(pdf_path: Path, asset: PaperAsset) -> None:
    metadata_path = pdf_path.with_suffix(".json")
    metadata = asdict(asset) | {
        "subject_name": english_subject_name(
            asset.exam_board,
            asset.qualification,
            asset.subject_code,
            asset.subject_name,
        ),
        "source_url": build_frank_cie_url(asset),
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

