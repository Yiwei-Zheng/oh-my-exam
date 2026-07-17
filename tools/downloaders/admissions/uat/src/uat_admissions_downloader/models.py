from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class ArchiveAsset:
    exam: str
    year: int
    document_type: str
    source_url: str

    def __post_init__(self) -> None:
        if self.exam not in {"engaa", "nsaa"}:
            raise ValueError(f"unsupported exam: {self.exam}")
        if self.document_type not in {"qp", "ms"}:
            raise ValueError(f"unsupported document type: {self.document_type}")

    @property
    def stem(self) -> str:
        return f"{self.exam}_{self.year}_s1_{self.document_type}"

    @property
    def relative_pdf_path(self) -> Path:
        return Path("uat") / "admissions" / self.exam / str(self.year) / "archive" / f"{self.stem}.pdf"
