from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


VARIANT_COMPONENTS = {"regular": "s1", "specimen": "s2"}
EXAM_BOARD = "pearson_vue"
SOURCE_PROVIDER = "pmt"


@dataclass(frozen=True, order=True)
class PatAsset:
    year: int
    variant: str
    document_type: str
    source_url: str

    def __post_init__(self) -> None:
        if self.variant not in VARIANT_COMPONENTS:
            raise ValueError(f"unsupported PAT variant: {self.variant}")
        if self.document_type not in {"qp", "ms"}:
            raise ValueError(f"unsupported document type: {self.document_type}")

    @property
    def component(self) -> str:
        return VARIANT_COMPONENTS[self.variant]

    @property
    def stem(self) -> str:
        return f"pat_{self.year}_{self.component}_{self.document_type}"

    @property
    def relative_pdf_path(self) -> Path:
        return Path(EXAM_BOARD) / "admissions" / "pat" / str(self.year) / self.variant / f"{self.stem}.pdf"
