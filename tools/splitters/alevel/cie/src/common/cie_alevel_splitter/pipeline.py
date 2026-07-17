from __future__ import annotations

import json
from pathlib import Path

from cie_alevel_splitter.database import connect, upsert_asset, upsert_mark_scheme_slice, upsert_question_slice
from cie_alevel_splitter.models import PaperAsset, QuestionSlice
from cie_alevel_splitter.pdf_splitter import split_pdf_by_question
from cie_alevel_splitter.subject_names import english_subject_name


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


def split_downloaded(raw_root: Path, processed_root: Path, report_path: Path, *, limit: int | None = None) -> dict[str, int]:
    metadata_paths = sorted(raw_root.rglob("*.json"))
    if limit is not None:
        metadata_paths = metadata_paths[:limit]
    counts = {"split": 0, "missing_pdf": 0, "failed": 0}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("a", encoding="utf-8") as report:
        for metadata_path in metadata_paths:
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
                    source_url=str(raw.get("source_url", "")),
                )
                pdf_path = raw_root / asset.relative_pdf_path
                if not pdf_path.exists():
                    counts["missing_pdf"] += 1
                    record = {"stem": asset.stem, "status": "missing_pdf"}
                else:
                    slices = split_asset_pdf(asset, raw_root, processed_root)
                    counts["split"] += 1
                    record = {"stem": asset.stem, "status": "split", "slices": len(slices)}
            except Exception as exc:
                counts["failed"] += 1
                record = {"metadata": str(metadata_path), "status": "failed", "message": str(exc)}
            report.write(json.dumps(record, ensure_ascii=False) + "\n")
            report.flush()
    return counts


def split_asset_pdf(asset: PaperAsset, raw_root: Path, processed_root: Path) -> list[QuestionSlice]:
    pdf_path = raw_root / asset.relative_pdf_path
    output_dir = processed_root / asset.exam_board / asset.qualification / asset.subject_code / asset.session / asset.stem
    return split_pdf_by_question(pdf_path, output_dir)


def ingest_slices(
    db_path: Path,
    asset: PaperAsset,
    raw_root: Path,
    question_slices: list[QuestionSlice],
    mark_scheme_slices: list[QuestionSlice] | None = None,
) -> None:
    with connect(db_path) as conn:
        paper_id = upsert_asset(conn, asset, raw_root / asset.relative_pdf_path)
        questions_by_number: dict[str, int] = {}
        for question in question_slices:
            questions_by_number[question.question_number] = upsert_question_slice(conn, paper_id, question)
        for mark_scheme in mark_scheme_slices or []:
            question_id = questions_by_number.get(mark_scheme.question_number)
            if question_id is not None:
                upsert_mark_scheme_slice(conn, question_id, mark_scheme)
