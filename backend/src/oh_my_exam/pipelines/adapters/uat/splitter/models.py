from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


STEM_RE = re.compile(
    r"(?P<exam>engaa|nsaa)_(?P<period>20\d{2})_(?P<component>s1)_(?P<type>qp|ms)$"
    r"|(?P<tmua>tmua)_(?P<tmua_period>20\d{2}|early_specimen)_"
    r"(?P<tmua_component>p[12])_(?P<tmua_type>qp|worked_answers)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PaperAsset:
    exam: str
    period: str
    component: str
    document_type: str
    pdf_path: Path
    source_url: str
    source_sha256: str
    source_document_type: str = ""

    @property
    def stem(self) -> str:
        return f"{self.exam}_{self.period}_{self.component}_{self.document_type}"

    @property
    def year(self) -> int | None:
        return int(self.period) if self.period.isdigit() else None

    @property
    def output_relative_dir(self) -> Path:
        return Path("uat") / "admissions" / self.exam / self.period / "archive" / self.component / self.document_type


def load_asset(pdf_path: Path) -> PaperAsset:
    match = STEM_RE.fullmatch(pdf_path.stem)
    if not match:
        raise ValueError(f"unsupported admissions archive filename: {pdf_path.name}")
    metadata_path = pdf_path.with_suffix(".json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
    is_tmua = match.group("tmua") is not None
    source_document_type = (match.group("tmua_type") if is_tmua else match.group("type")).lower()
    return PaperAsset(
        exam="tmua" if is_tmua else match.group("exam").lower(),
        period=(match.group("tmua_period") if is_tmua else match.group("period")).lower(),
        component=(match.group("tmua_component") if is_tmua else match.group("component")).lower(),
        document_type="ms" if source_document_type == "worked_answers" else source_document_type,
        pdf_path=pdf_path,
        source_url=str(metadata.get("source_url", "")),
        source_sha256=str(metadata.get("source_pdf_sha256", "")),
        source_document_type=source_document_type,
    )
