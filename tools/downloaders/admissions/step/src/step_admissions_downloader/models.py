from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


EXAM_BOARD = "ocr"
SOURCE_PROVIDER = "pmt"


@dataclass(frozen=True, order=True)
class StepAsset:
    year: int
    paper: int
    document_type: str
    source_url: str
    contains_papers: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.paper <= 3:
            raise ValueError(f"unsupported STEP paper: {self.paper}")
        if self.document_type not in {"qp", "ms"}:
            raise ValueError(f"unsupported document type: {self.document_type}")
        if self.contains_papers and any(paper not in {1, 2, 3} for paper in self.contains_papers):
            raise ValueError(f"unsupported bundled STEP papers: {self.contains_papers}")

    @property
    def component(self) -> str:
        return f"s{self.paper}"

    @property
    def stem(self) -> str:
        return f"step_{self.year}_{self.component}_{self.document_type}"

    @property
    def relative_pdf_path(self) -> Path:
        return Path(EXAM_BOARD) / "admissions" / "step" / str(self.year) / "archive" / f"{self.stem}.pdf"
