from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


STEM_RE = re.compile(r"pat_(?P<year>\d{4})_s(?P<component>[12])_(?P<type>qp|ms)$", re.IGNORECASE)
COMPONENT_VARIANTS = {1: "regular", 2: "specimen"}
EXAM_BOARD = "pearson_vue"


@dataclass(frozen=True)
class PaperAsset:
    year: int
    component: int
    document_type: str
    pdf_path: Path
    source_url: str
    source_sha256: str

    @property
    def variant(self) -> str:
        return COMPONENT_VARIANTS[self.component]

    @property
    def stem(self) -> str:
        return self.pdf_path.stem

    @property
    def output_relative_dir(self) -> Path:
        return Path(EXAM_BOARD) / "admissions" / "pat" / str(self.year) / self.variant / f"s{self.component}" / self.document_type


def load_asset(pdf_path: Path) -> PaperAsset:
    match = STEM_RE.fullmatch(pdf_path.stem)
    if not match:
        raise ValueError(f"unsupported PAT archive filename: {pdf_path.name}")
    metadata_path = pdf_path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return PaperAsset(
        year=int(match.group("year")),
        component=int(match.group("component")),
        document_type=match.group("type").lower(),
        pdf_path=pdf_path,
        source_url=str(metadata.get("source_url", "")),
        source_sha256=str(metadata.get("source_pdf_sha256", "")),
    )
