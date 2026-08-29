from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import urllib.error
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from oh_my_exam.paths import BACKEND_ROOT
from typing import Iterable

from oh_my_exam.pipelines.adapters.cie_alevel.downloader.models import PaperAsset


FRANK_BASE_URL = "https://cie.fraft.cn"
DEFAULT_AVAILABILITY_INDEX = BACKEND_ROOT / "resources/exam_boards/cie/frank_available_assets.json"
DEFAULT_SUBJECT_AVAILABILITY_DIR = BACKEND_ROOT / "resources/exam_boards/cie/available_assets"
FRANK_SEASONS = {"Mar": "m", "Jun": "s", "Nov": "w"}
SESSION_TO_FRANK_SEASON = {value: key for key, value in FRANK_SEASONS.items()}


def fetch_frank_subjects(*, timeout_seconds: float = 20.0) -> list[dict[str, str]]:
    data = _post_json("obj/Common/Subject/combo", {}, timeout_seconds=timeout_seconds)
    subjects: list[dict[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        value = str(item.get("value", "")).strip()
        text = str(item.get("text", "")).strip()
        if value:
            subjects.append({"code": value, "text": text})
    return subjects


def fetch_frank_files(subject: str, year: int, season: str, *, timeout_seconds: float = 20.0) -> list[str]:
    data = _post_json(
        "obj/Common/Fetch/renum",
        {"subject": subject, "year": str(year), "season": season},
        timeout_seconds=timeout_seconds,
    )
    if not isinstance(data, dict):
        return []
    rows = data.get("rows")
    if not isinstance(rows, list):
        return []
    files: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        file_name = str(row.get("file", "")).strip()
        if file_name.endswith(".pdf"):
            files.append(file_name)
    return files


def discover_frank_assets(
    *,
    qualification: str = "a_level",
    subject_codes: set[str] | None = None,
    start_year: int = 2001,
    end_year: int | None = None,
    seasons: Iterable[str] = ("Mar", "Jun", "Nov"),
    delay_seconds: float = 0.2,
    workers: int = 1,
    timeout_seconds: float = 20.0,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> list[PaperAsset]:
    end_year = end_year or datetime.now().year
    frank_subjects = fetch_frank_subjects(timeout_seconds=timeout_seconds)
    frank_subjects = [
        subject
        for subject in frank_subjects
        if _subject_matches_qualification(subject["text"], qualification)
        and (subject_codes is None or subject["code"] in subject_codes)
    ]
    subject_names = {subject["code"]: _clean_subject_name(subject["text"]) for subject in frank_subjects}
    jobs = [
        (subject["code"], year, season)
        for subject in frank_subjects
        for year in range(start_year, end_year + 1)
        for season in seasons
    ]
    assets_by_stem: dict[str, PaperAsset] = {}
    workers = max(1, int(workers))

    def fetch_job(job: tuple[str, int, str]) -> tuple[tuple[str, int, str], list[str], str | None]:
        code, year, season = job
        error = None
        try:
            files = fetch_frank_files(code, year, season, timeout_seconds=timeout_seconds)
        except Exception as exc:  # A single flaky Frank query should not abort the whole availability sync.
            files = []
            error = str(exc)
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        return job, files, error

    completed = 0
    if workers == 1:
        for job in jobs:
            _, files, error = fetch_job(job)
            completed += 1
            _add_files(assets_by_stem, files, subject_names, qualification)
            if progress:
                progress({"completed": completed, "total": len(jobs), "assets": len(assets_by_stem), "job": job, "error": error})
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_jobs = {executor.submit(fetch_job, job): job for job in jobs}
            for future in as_completed(future_jobs):
                job, files, error = future.result()
                completed += 1
                _add_files(assets_by_stem, files, subject_names, qualification)
                if progress:
                    progress({"completed": completed, "total": len(jobs), "assets": len(assets_by_stem), "job": job, "error": error})

    return sorted(assets_by_stem.values(), key=lambda asset: (asset.subject_code, asset.session, asset.document_type, asset.component))


def save_availability_index(
    path: Path,
    assets: list[PaperAsset],
    *,
    source: str = FRANK_BASE_URL,
    coverage: list[dict[str, object]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": coverage or [],
        "assets": [asdict(asset) | {"stem": asset.stem} for asset in assets],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_availability_index(path: Path) -> list[PaperAsset]:
    raw = load_availability_payload(path)
    records = raw.get("assets", raw)
    if not isinstance(records, list):
        raise ValueError("availability index must contain an assets list")
    assets: list[PaperAsset] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        assets.append(
            PaperAsset(
                exam_board=str(record.get("exam_board", "cie")),
                qualification=str(record.get("qualification", "a_level")),
                subject_code=str(record["subject_code"]),
                subject_name=str(record.get("subject_name", record["subject_code"])),
                session=str(record["session"]),
                document_type=str(record["document_type"]),
                component=str(record.get("component", "")),
            )
        )
    return assets


def load_availability_payload(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(raw, list):
        return {"assets": raw, "coverage": []}
    if not isinstance(raw, dict):
        raise ValueError("availability index must be a JSON object or assets list")
    return raw


def subject_availability_path(
    subject_code: str,
    *,
    qualification: str = "a_level",
    availability_dir: Path = DEFAULT_SUBJECT_AVAILABILITY_DIR,
) -> Path:
    return availability_dir / qualification / f"{subject_code}.json"


def load_subject_availability_assets(
    subject_codes: set[str],
    *,
    qualification: str = "a_level",
    availability_dir: Path = DEFAULT_SUBJECT_AVAILABILITY_DIR,
) -> list[PaperAsset]:
    assets: list[PaperAsset] = []
    for code in sorted(subject_codes):
        path = subject_availability_path(code, qualification=qualification, availability_dir=availability_dir)
        if path.exists():
            assets.extend(load_availability_index(path))
    return sorted(assets, key=lambda asset: (asset.subject_code, asset.session, asset.document_type, asset.component))


def availability_covers_request(
    path: Path,
    *,
    subject_code: str,
    start_year: int,
    end_year: int,
    seasons: Iterable[str] = ("Mar", "Jun", "Nov"),
) -> bool:
    if not path.exists():
        return False
    payload = load_availability_payload(path)
    coverage = payload.get("coverage", [])
    if not isinstance(coverage, list):
        return False
    requested = {(year, season) for year in range(start_year, end_year + 1) for season in seasons}
    covered: set[tuple[int, str]] = set()
    for block in coverage:
        if not isinstance(block, dict) or str(block.get("subject_code")) != subject_code:
            continue
        block_start = int(block.get("start_year", 0))
        block_end = int(block.get("end_year", -1))
        block_seasons = {str(season) for season in block.get("seasons", [])}
        for year in range(block_start, block_end + 1):
            for season in block_seasons:
                covered.add((year, season))
    return requested.issubset(covered)


def subjects_missing_availability(
    subject_codes: set[str],
    *,
    qualification: str = "a_level",
    start_year: int,
    end_year: int,
    seasons: Iterable[str] = ("Mar", "Jun", "Nov"),
    availability_dir: Path = DEFAULT_SUBJECT_AVAILABILITY_DIR,
) -> set[str]:
    return {
        code
        for code in subject_codes
        if not availability_covers_request(
            subject_availability_path(code, qualification=qualification, availability_dir=availability_dir),
            subject_code=code,
            start_year=start_year,
            end_year=end_year,
            seasons=seasons,
        )
    }


def ensure_subject_availability(
    subject_codes: set[str],
    *,
    qualification: str = "a_level",
    start_year: int,
    end_year: int,
    seasons: Iterable[str] = ("Mar", "Jun", "Nov"),
    availability_dir: Path = DEFAULT_SUBJECT_AVAILABILITY_DIR,
    force: bool = False,
    delay_seconds: float = 0.2,
    workers: int = 1,
    timeout_seconds: float = 20.0,
    progress: Callable[[dict[str, object]], None] | None = None,
) -> dict[str, object]:
    season_list = list(seasons)
    missing = set(subject_codes) if force else subjects_missing_availability(
        subject_codes,
        qualification=qualification,
        start_year=start_year,
        end_year=end_year,
        seasons=season_list,
        availability_dir=availability_dir,
    )
    sniffed: list[str] = []
    failures = 0
    for code in sorted(missing):
        path = subject_availability_path(code, qualification=qualification, availability_dir=availability_dir)
        existing_assets = load_availability_index(path) if path.exists() else []
        existing_payload = load_availability_payload(path) if path.exists() else {"coverage": []}
        subject_failures = 0

        def subject_progress(event: dict[str, object]) -> None:
            nonlocal subject_failures
            if event.get("error"):
                subject_failures += 1
            if progress:
                progress({"subject_code": code, **event})

        discovered = discover_frank_assets(
            qualification=qualification,
            subject_codes={code},
            start_year=start_year,
            end_year=end_year,
            seasons=season_list,
            delay_seconds=delay_seconds,
            workers=workers,
            timeout_seconds=timeout_seconds,
            progress=subject_progress,
        )
        merged_assets = {asset.stem: asset for asset in existing_assets}
        merged_assets.update({asset.stem: asset for asset in discovered})
        coverage = [block for block in existing_payload.get("coverage", []) if isinstance(block, dict)]
        coverage.append(
            {
                "subject_code": code,
                "qualification": qualification,
                "start_year": start_year,
                "end_year": end_year,
                "seasons": season_list,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "failed_queries": subject_failures,
            }
        )
        save_availability_index(path, sorted(merged_assets.values(), key=lambda asset: asset.stem), coverage=coverage)
        sniffed.append(code)
        failures += subject_failures
    return {"sniffed_subjects": sniffed, "failed_queries": failures}


def filter_to_available_assets(candidates: list[PaperAsset], availability_index: Path | None) -> list[PaperAsset]:
    if availability_index is None or not availability_index.exists():
        return candidates
    available_stems = {asset.stem for asset in load_availability_index(availability_index)}
    return [asset for asset in candidates if asset.stem in available_stems]


def estimate_crawl_seconds(asset_count: int, *, delay_seconds: float, workers: int) -> float:
    if asset_count <= 0:
        return 0.0
    return asset_count * max(0.0, delay_seconds) / max(1, int(workers))


def format_duration(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def _add_files(
    assets_by_stem: dict[str, PaperAsset],
    files: list[str],
    subject_names: dict[str, str],
    qualification: str,
) -> None:
    for file_name in files:
        asset = _asset_from_frank_file(file_name, subject_names, qualification)
        if asset is not None:
            assets_by_stem[asset.stem] = asset


def _asset_from_frank_file(file_name: str, subject_names: dict[str, str], qualification: str) -> PaperAsset | None:
    name = file_name.removesuffix(".pdf")
    parts = name.split("_")
    if len(parts) < 3:
        return None
    code, session, document_type = parts[0], parts[1], parts[2]
    if len(code) != 4 or not code.isdigit() or len(session) != 3:
        return None
    component = "_".join(parts[3:])
    if document_type == "ms" and "+" in component:
        return None
    if document_type not in {"qp", "ms"}:
        return None
    return PaperAsset(
        exam_board="cie",
        qualification=qualification,
        subject_code=code,
        subject_name=subject_names.get(code, code),
        session=session,
        document_type=document_type,
        component=component,
    )


def _post_json(endpoint: str, data: dict[str, str], *, timeout_seconds: float) -> object:
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(
        f"{FRANK_BASE_URL}/{endpoint}",
        data=body,
        headers={"User-Agent": "Oh-My-Exam/0.1", "Content-Type": "application/x-www-form-urlencoded"},
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            return json.loads(urllib.request.urlopen(request, timeout=timeout_seconds).read().decode("utf-8", "replace"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"Frank API request failed for {endpoint}: {last_error}") from last_error


def _subject_matches_qualification(text: str, qualification: str) -> bool:
    if qualification == "a_level":
        return "(AS/A2)" in text
    if qualification == "igcse":
        return "(IGCSE)" in text
    return True


def _clean_subject_name(text: str) -> str:
    value = text
    if " - " in value:
        value = value.split(" - ", 1)[1]
    value = value.replace("🔥", "").replace("视频课速通", "")
    value = value.replace("(AS/A2)", "").replace("(IGCSE)", "")
    return " ".join(value.split()).strip(" -") or text

