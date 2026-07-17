from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PaperAsset:
    exam_board: str
    qualification: str
    subject_code: str
    subject_name: str
    session: str
    document_type: str
    component: str
    source_url: str = ""

    @property
    def stem(self) -> str:
        base = f"{self.subject_code}_{self.session}_{self.document_type}"
        return f"{base}_{self.component}" if self.component else base

    @property
    def year(self) -> int:
        return 2000 + int(self.session[1:3])

    @property
    def relative_pdf_path(self) -> Path:
        return Path(self.exam_board) / self.qualification / self.subject_code / str(self.year) / self.session / f"{self.stem}.pdf"

    @property
    def legacy_relative_pdf_path(self) -> Path:
        return Path(self.exam_board) / self.qualification / self.subject_code / self.session / f"{self.stem}.pdf"


@dataclass(frozen=True)
class QuestionSlice:
    question_number: str
    source_stem: str
    pdf_path: Path
    page_start: int
    page_end: int
    content: str = ""
    mark_scheme_points: tuple[dict[str, Any], ...] = ()
