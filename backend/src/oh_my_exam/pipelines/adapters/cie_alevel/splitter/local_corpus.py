from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from oh_my_exam.pipelines.adapters.cie_alevel.splitter.models import PaperAsset
from oh_my_exam.pipelines.adapters.cie_alevel.splitter.subject_names import english_subject_name


@dataclass(frozen=True)
class InstalledPaperSet:
    exam_board: str
    qualification: str
    subject_code: str
    subject_name: str
    year: int
    session: str
    component: str
    qp: PaperAsset | None
    ms: PaperAsset | None

    @property
    def key(self) -> str:
        return f"{self.exam_board}/{self.qualification}/{self.subject_code}/{self.year}/{self.session}/{self.component}"

    @property
    def label(self) -> str:
        return f"{self.subject_code} {self.subject_name} {self.session} {self.component}"


def discover_installed_paper_sets(raw_root: Path) -> list[InstalledPaperSet]:
    pairs: dict[tuple[str, str, str, int, str, str], dict[str, PaperAsset]] = {}
    componentless_mark_schemes: dict[tuple[str, str, str, int, str], PaperAsset] = {}
    subject_names: dict[tuple[str, str, str], str] = {}
    metadata_root = raw_root / "cie" / "a_level"
    if not metadata_root.exists():
        return []
    for metadata_path in sorted(metadata_root.rglob("*.json")):
        try:
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
            subject_name = english_subject_name(
                raw["exam_board"],
                raw["qualification"],
                raw["subject_code"],
                raw["subject_name"],
            )
            asset = PaperAsset(
                exam_board=raw["exam_board"],
                qualification=raw["qualification"],
                subject_code=raw["subject_code"],
                subject_name=subject_name,
                session=raw["session"],
                document_type=raw["document_type"],
                component=str(raw["component"]),
                source_url=str(raw.get("source_url", "")),
            )
        except (KeyError, OSError, json.JSONDecodeError):
            continue
        pdf_path = raw_root / asset.relative_pdf_path
        if not pdf_path.exists():
            continue
        if asset.document_type == "ms" and not asset.component:
            componentless_mark_schemes[(asset.exam_board, asset.qualification, asset.subject_code, asset.year, asset.session)] = asset
        else:
            key = (asset.exam_board, asset.qualification, asset.subject_code, asset.year, asset.session, asset.component)
            pairs.setdefault(key, {})[asset.document_type] = asset
        subject_names[(asset.exam_board, asset.qualification, asset.subject_code)] = asset.subject_name

    installed: list[InstalledPaperSet] = []
    for key, docs in pairs.items():
        exam_board, qualification, subject_code, year, session, component = key
        fallback_ms = componentless_mark_schemes.get((exam_board, qualification, subject_code, year, session))
        installed.append(
            InstalledPaperSet(
                exam_board=exam_board,
                qualification=qualification,
                subject_code=subject_code,
                subject_name=subject_names.get((exam_board, qualification, subject_code), subject_code),
                year=year,
                session=session,
                component=component,
                qp=docs.get("qp"),
                ms=docs.get("ms") or fallback_ms,
            )
        )
    return sorted(installed, key=lambda item: (item.subject_code, item.year, item.session, item.component))


def filter_paper_sets(
    paper_sets: list[InstalledPaperSet],
    *,
    keys: set[str] | None = None,
    subject_codes: set[str] | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    require_qp: bool = False,
    require_ms: bool = False,
) -> list[InstalledPaperSet]:
    selected: list[InstalledPaperSet] = []
    for paper_set in paper_sets:
        if keys and paper_set.key not in keys:
            continue
        if subject_codes and paper_set.subject_code not in subject_codes:
            continue
        if start_year is not None and paper_set.year < start_year:
            continue
        if end_year is not None and paper_set.year > end_year:
            continue
        if require_qp and paper_set.qp is None:
            continue
        if require_ms and paper_set.ms is None:
            continue
        selected.append(paper_set)
    return selected

