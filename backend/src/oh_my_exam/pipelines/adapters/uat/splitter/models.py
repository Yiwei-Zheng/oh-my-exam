from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


STEM_RE = re.compile(r"(?P<exam>engaa|nsaa)_(?P<year>20\d{2})_s1_(?P<type>qp|ms)$", re.IGNORECASE)


@dataclass(frozen=True)
class PaperAsset:
    exam: str
    year: int
    document_type: str
    pdf_path: Path
    source_url: str
    source_sha256: str

    @property
    def stem(self) -> str:
        return self.pdf_path.stem

    @property
    def output_relative_dir(self) -> Path:
        return Path("uat") / "admissions" / self.exam / str(self.year) / "archive" / "s1" / self.document_type


def load_asset(pdf_path: Path) -> PaperAsset:
    match = STEM_RE.fullmatch(pdf_path.stem)
    if not match:
        raise ValueError(f"unsupported admissions archive filename: {pdf_path.name}")
    metadata_path = pdf_path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    return PaperAsset(
        exam=match.group("exam").lower(),
        year=int(match.group("year")),
        document_type=match.group("type").lower(),
        pdf_path=pdf_path,
        source_url=str(metadata.get("source_url", "")),
        source_sha256=str(metadata.get("source_pdf_sha256", "")),
    )
