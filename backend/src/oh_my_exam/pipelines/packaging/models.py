from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SOURCE_TYPES = {"QP", "MS"}


@dataclass(frozen=True)
class PackOptions:
    metadata_root: Path
    output_dir: Path
    qualification: str
    exam_board: str
    course_code: str
    overwrite: bool = False
    dry_run: bool = False
    course_display_name: str = ""


@dataclass(frozen=True)
class MetadataCourse:
    qualification: str
    exam_board: str
    course_code: str
    metadata_count: int

    @property
    def key(self) -> str:
        return f"{self.exam_board}/{self.qualification}/{self.course_code}"


@dataclass
class MetadataRecord:
    metadata_path: Path
    metadata: dict[str, Any]
    exam_board: str
    qualification: str
    course_code: str
    session: str
    year: int
    paper_code: str
    variant: str
    component: str
    paper_key: str
    source_type: str
    source_stem: str
    source_url: str
    question_key: str
    local_question_key: str
    image_path: Path | None
    crop_regions: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    records: list[MetadataRecord]
    warnings: list[str]
    matched_pairs: int
    only_qp: int
    only_ms: int
    duplicate_qp: int
    duplicate_ms: int
    ambiguous_match: int


@dataclass
class PackSummary:
    metadata_count: int = 0
    matched_pairs: int = 0
    only_qp: int = 0
    only_ms: int = 0
    duplicate_qp: int = 0
    duplicate_ms: int = 0
    ambiguous_match: int = 0
    papers_written: int = 0
    questions_written: int = 0
    crop_regions_written: int = 0
    question_texts_written: int = 0
    question_images_written: int = 0
    database_path: Path | None = None
    warnings: list[str] = field(default_factory=list)

    def as_lines(self) -> list[str]:
        path = str(self.database_path) if self.database_path else ""
        return [
            f"metadata_count={self.metadata_count}",
            f"matched_pairs={self.matched_pairs}",
            f"only_qp={self.only_qp}",
            f"only_ms={self.only_ms}",
            f"duplicate_qp={self.duplicate_qp}",
            f"duplicate_ms={self.duplicate_ms}",
            f"ambiguous_match={self.ambiguous_match}",
            f"papers_written={self.papers_written}",
            f"questions_written={self.questions_written}",
            f"crop_regions_written={self.crop_regions_written}",
            f"question_texts_written={self.question_texts_written}",
            f"question_images_written={self.question_images_written}",
            f"database_path={path}",
        ]
