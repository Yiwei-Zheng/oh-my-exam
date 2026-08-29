from __future__ import annotations

import re
from dataclasses import dataclass


QUESTION_START_RE = re.compile(r"^\s*(\d{1,2})\s+(?:\(|[A-Z0-9])")
MARK_POINT_RE = re.compile(r"\b(?P<kind>[MAB])(?P<number>\d+)\b")


@dataclass(frozen=True)
class MarkPoint:
    mark_type: str
    marker: str
    text: str


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_mostly_blank(text: str, *, min_non_space_chars: int = 20) -> bool:
    compact = re.sub(r"\s+", "", text)
    return len(compact) < min_non_space_chars


def detect_question_number(text: str) -> str | None:
    for line in normalize_text(text).splitlines():
        match = QUESTION_START_RE.match(line)
        if match:
            return match.group(1)
    return None


def parse_mark_points(mark_scheme_text: str) -> list[MarkPoint]:
    points: list[MarkPoint] = []
    for line in normalize_text(mark_scheme_text).splitlines():
        match = MARK_POINT_RE.search(line)
        if not match:
            continue
        points.append(
            MarkPoint(
                mark_type=match.group("kind"),
                marker=match.group(0),
                text=line.strip(),
            )
        )
    return points


