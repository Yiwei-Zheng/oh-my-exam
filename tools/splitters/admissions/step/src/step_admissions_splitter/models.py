from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


STEM_RE = re.compile(r"step_(?P<year>\d{4})_s(?P<paper>[123])_(?P<type>qp|ms)$", re.IGNORECASE)
EXAM_BOARD = "ocr"


@dataclass(frozen=True)
class PaperAsset:
    year: int
    paper: int
    document_type: str
    pdf_path: Path
    source_url: str
    source_sha256: str
    contains_papers: tuple[int, ...] = ()

    @property
    def stem(self) -> str:
        return self.pdf_path.stem

    @property
    def output_relative_dir(self) -> Path:
        return Path(EXAM_BOARD) / "admissions" / "step" / str(self.year) / "archive" / f"s{self.paper}" / self.document_type


def load_asset(pdf_path: Path) -> PaperAsset:
    match = STEM_RE.fullmatch(pdf_path.stem)
    if not match:
        raise ValueError(f"unsupported STEP archive filename: {pdf_path.name}")
    metadata_path = pdf_path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    contains_papers = tuple(int(paper) for paper in metadata.get("contains_papers", ()))
    return PaperAsset(
        year=int(match.group("year")),
        paper=int(match.group("paper")),
        document_type=match.group("type").lower(),
        pdf_path=pdf_path,
        source_url=str(metadata.get("source_url", "")),
        source_sha256=str(metadata.get("source_pdf_sha256", "")),
        contains_papers=contains_papers,
    )
