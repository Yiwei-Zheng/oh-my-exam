from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from oh_my_exam.pipelines.adapters.step.splitter.cutter import SplitOptions, split_asset
from oh_my_exam.pipelines.adapters.step.splitter.models import EXAM_BOARD, load_asset


def discover_downloaded(raw_root: Path) -> list[Path]:
    base = raw_root / EXAM_BOARD / "admissions" / "step"
    return sorted(path for path in base.glob("????/archive/step_????_s[123]_[qm][ps].pdf") if path.is_file()) if base.exists() else []


def split_downloaded(
    raw_root: Path,
    processed_root: Path,
    report_path: Path,
    *,
    papers: set[int] | None = None,
    document_types: set[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int | None = None,
    options: SplitOptions | None = None,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, int]:
    assets = [load_asset(path) for path in discover_downloaded(raw_root)]
    assets = [
        asset for asset in assets
        if (not papers or asset.paper in papers)
        and (not document_types or asset.document_type in document_types)
        and (start_year is None or asset.year >= start_year)
        and (end_year is None or asset.year <= end_year)
    ]
    if limit is not None:
        assets = assets[:limit]
    counts = {"split": 0, "failed": 0}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as report:
        for asset in assets:
            try:
                outputs = split_asset(asset, processed_root, options)
                status = "split"
                record: dict[str, object] = {"asset": asset.stem, "status": status, "questions": len(outputs)}
            except Exception as exc:
                status = "failed"
                record = {"asset": asset.stem, "status": status, "message": str(exc)}
            counts[status] += 1
            report.write(json.dumps(record, ensure_ascii=False) + "\n")
            report.flush()
            if progress:
                progress(record)
    return counts
