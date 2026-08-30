from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from oh_my_exam.pipelines.adapters.uat.splitter.cutter import SplitOptions, load_tmua_answer_keys, split_asset
from oh_my_exam.pipelines.adapters.uat.splitter.models import load_asset


def discover_downloaded(raw_root: Path) -> list[Path]:
    base = raw_root / "uat" / "admissions"
    if not base.exists():
        return []
    standard = base.glob("*/20??/archive/*_s1_*.pdf")
    tmua = (base / "tmua").glob("*/archive/tmua_*_p[12]_*.pdf")
    return sorted(path for path in (*standard, *tmua) if path.is_file())


def split_downloaded(
    raw_root: Path,
    processed_root: Path,
    report_path: Path,
    *,
    exams: set[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    limit: int | None = None,
    options: SplitOptions | None = None,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, int]:
    assets = [load_asset(path) for path in discover_downloaded(raw_root)]
    assets = [
        asset for asset in assets
        if (not exams or asset.exam in exams)
        and (asset.year is None or start_year is None or asset.year >= start_year)
        and (asset.year is None or end_year is None or asset.year <= end_year)
    ]
    if limit is not None:
        assets = assets[:limit]
    counts = {"split": 0, "failed": 0}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as report:
        for asset in assets:
            try:
                answer_choices = None
                if asset.exam == "tmua" and asset.document_type == "ms":
                    key_path = asset.pdf_path.parent / f"tmua_{asset.period}_ms.pdf"
                    answer_choices = load_tmua_answer_keys(key_path)[asset.component]
                outputs = split_asset(asset, processed_root, options, answer_choices=answer_choices)
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
