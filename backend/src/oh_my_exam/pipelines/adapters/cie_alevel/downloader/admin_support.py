"""Read models used by the administrator pipeline UI."""

from __future__ import annotations

import json
from pathlib import Path

from .frank_discovery import load_availability_index, subject_availability_path
from .pipeline import filter_assets


PROJECT_ROOT = Path(__file__).resolve().parents[7]
DEFAULT_MANIFEST = Path("backend/resources/exam_boards/cie/cie_a_level_subject_rules.json")
FALLBACK_MANIFEST = Path("backend/config/exams/cie_a_level_through_2025_manifest.json")


def project_path(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def load_subject_options(manifest_path: Path) -> dict[str, str]:
    raw = json.loads(project_path(manifest_path).read_text(encoding="utf-8-sig"))
    options: dict[str, str] = {}
    for subject in raw.get("subjects", []):
        if not isinstance(subject, dict):
            continue
        code = str(subject.get("code", "")).strip()
        name = str(subject.get("name", "")).strip()
        if code:
            options[code] = name or code
    return dict(sorted(options.items(), key=lambda item: (item[1].lower(), item[0])))


def default_manifest_path() -> Path:
    return DEFAULT_MANIFEST if project_path(DEFAULT_MANIFEST).exists() else FALLBACK_MANIFEST


def local_pdf_relative_paths(raw_root: Path) -> set[str]:
    if not raw_root.exists():
        return set()
    return {
        path.relative_to(raw_root).as_posix().lower()
        for path in raw_root.rglob("*.pdf")
        if path.is_file() and path.stat().st_size > 0
    }


def subject_download_percentage(
    subject_code: str,
    *,
    raw_root: Path,
    availability_dir: Path,
    start_year: int,
    end_year: int,
    document_types: set[str],
    qualification: str = "a_level",
    local_pdfs: set[str] | None = None,
) -> int:
    path = subject_availability_path(
        subject_code,
        qualification=qualification,
        availability_dir=availability_dir,
    )
    if not path.exists():
        return 0
    assets = filter_assets(
        load_availability_index(path),
        subject_codes={subject_code},
        document_types=document_types,
        start_year=start_year,
        end_year=end_year,
    )
    if not assets:
        return 0
    installed = local_pdfs if local_pdfs is not None else local_pdf_relative_paths(raw_root)
    downloaded = sum(
        1
        for asset in assets
        if asset.relative_pdf_path.as_posix().lower() in installed
        or asset.legacy_relative_pdf_path.as_posix().lower() in installed
    )
    return round(downloaded * 100 / len(assets))
