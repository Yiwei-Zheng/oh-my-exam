from __future__ import annotations

import re
import shutil
import tempfile
import uuid
from pathlib import Path

from exam_packer.metadata_loader import discover_metadata_courses, load_metadata_records
from exam_packer.models import MetadataCourse, PackOptions, PackSummary
from exam_packer.question_matcher import match_metadata_records
from exam_packer.sqlite_writer import write_records

__all__ = ["MetadataCourse", "discover_metadata_courses", "pack_subject_database"]


def pack_subject_database(options: PackOptions) -> PackSummary:
    exam_board = _snake_case(options.exam_board)
    qualification = _snake_case(options.qualification)
    course_code = _snake_case(options.course_code)
    db_path = options.output_dir / f"{exam_board}_{qualification}_{course_code}.sqlite"
    records, warnings = load_metadata_records(
        options.metadata_root,
        exam_board=exam_board,
        qualification=qualification,
        course_code=course_code,
    )
    matched = match_metadata_records(records)
    summary = PackSummary(
        metadata_count=len(records),
        matched_pairs=matched.matched_pairs,
        only_qp=matched.only_qp,
        only_ms=matched.only_ms,
        duplicate_qp=matched.duplicate_qp,
        duplicate_ms=matched.duplicate_ms,
        ambiguous_match=matched.ambiguous_match,
        database_path=db_path,
        warnings=[*warnings, *matched.warnings],
    )
    if options.dry_run:
        return summary
    db_path.parent.mkdir(parents=True, exist_ok=True)
    writer_options = PackOptions(
        metadata_root=options.metadata_root,
        output_dir=options.output_dir,
        qualification=qualification,
        exam_board=exam_board,
        course_code=course_code,
        overwrite=options.overwrite,
        dry_run=options.dry_run,
        course_display_name=options.course_display_name,
    )
    work_path = _prepare_working_database(db_path, overwrite=options.overwrite)
    try:
        result = write_records(work_path, writer_options, matched.records, summary)
        _replace_final_database(work_path, db_path)
        return result
    finally:
        _remove_sqlite_database_files(work_path)


def _snake_case(value: str) -> str:
    clean = re.sub(r"[^0-9A-Za-z]+", "_", value.strip()).strip("_").lower()
    return clean or "unknown"


def _remove_sqlite_database_files(db_path: Path) -> None:
    for path in (
        db_path,
        db_path.with_name(f"{db_path.name}-journal"),
        db_path.with_name(f"{db_path.name}-wal"),
        db_path.with_name(f"{db_path.name}-shm"),
    ):
        if path.exists():
            path.unlink()


def _prepare_working_database(db_path: Path, *, overwrite: bool) -> Path:
    work_path = Path(tempfile.gettempdir()) / f"ome_packer_{uuid.uuid4().hex}_{db_path.name}"
    _remove_sqlite_database_files(work_path)
    if db_path.exists() and not overwrite:
        shutil.copy2(db_path, work_path)
    return work_path


def _replace_final_database(work_path: Path, db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _remove_sqlite_database_files(db_path)
        shutil.copy2(work_path, db_path)
    except PermissionError as exc:
        raise PermissionError(f"failed to replace {db_path}; close DB Browser or any process using this database and retry") from exc
