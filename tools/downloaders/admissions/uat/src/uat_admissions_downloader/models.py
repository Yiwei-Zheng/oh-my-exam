from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ArchiveAsset:
    exam: str
    year: int | None
    document_type: str
    source_url: str
    component: str = "s1"
    edition: str = "archive"

    def __post_init__(self) -> None:
        if self.exam not in {"engaa", "nsaa", "tmua"}:
            raise ValueError(f"unsupported exam: {self.exam}")
        if self.document_type not in {"qp", "ms", "worked_answers"}:
            raise ValueError(f"unsupported document type: {self.document_type}")
        if self.year is None and self.edition == "archive":
            raise ValueError("archive assets require a year")

    @property
    def stem(self) -> str:
        period = str(self.year) if self.year is not None else self.edition
        component = f"_{self.component}" if self.component else ""
        return f"{self.exam}_{period}{component}_{self.document_type}"

    @property
    def relative_pdf_path(self) -> Path:
        period = str(self.year) if self.year is not None else self.edition
        return Path("uat") / "admissions" / self.exam / period / "archive" / f"{self.stem}.pdf"
