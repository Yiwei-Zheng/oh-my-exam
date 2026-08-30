from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3

import pymupdf


BOILERPLATE_LINES = (
    re.compile(r"^(?:https?://)?(?:www\.)?physicsandmathstutor\.com/?$", re.IGNORECASE),
    re.compile(r"^step\s+(?:i{1,3}|\d+).*(?:hints and answers|solutions|examiner(?:s'|’)? report)", re.IGNORECASE),
    re.compile(r"^june\s+\d{4}$", re.IGNORECASE),
    re.compile(r"^report on the components.*$", re.IGNORECASE),
    re.compile(r"^©\s*(?:uccles|ucies|ucales|ucles|ocr).*$", re.IGNORECASE),
    re.compile(r"^\[?turn over\]?$", re.IGNORECASE),
)


@dataclass(frozen=True)
class AnswerExtractionSummary:
    answers_seen: int
    versions_written: int
    empty_answers: int


def extract_answer_markdown(
    database_path: Path,
    paper_root: Path,
    *,
    overwrite: bool = False,
) -> AnswerExtractionSummary:
    database_path = database_path.resolve()
    paper_root = paper_root.resolve()
    if not database_path.is_file():
        raise ValueError(f"global catalog does not exist: {database_path}")
    if not paper_root.is_dir():
        raise ValueError(f"paper root does not exist: {paper_root}")

    with closing(sqlite3.connect(database_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT a.id AS answer_id, pd.storage_key,
                   ar.region_order, ar.page_index, ar.x0, ar.y0, ar.x1, ar.y1,
                   ar.render_dpi, ar.post_left, ar.post_top, ar.post_right, ar.post_bottom
            FROM answers a
            JOIN paper_documents pd ON pd.id = a.source_document_id
            JOIN answer_regions ar ON ar.answer_id = a.id
            ORDER BY pd.storage_key, a.id, ar.region_order
            """
        ).fetchall()
        grouped: dict[tuple[str, int], list[sqlite3.Row]] = defaultdict(list)
        for row in rows:
            grouped[(str(row["storage_key"]), int(row["answer_id"]))].append(row)

        seen = len(grouped)
        written = 0
        empty = 0
        current_key: str | None = None
        document: pymupdf.Document | None = None
        try:
            for (storage_key, answer_id), regions in grouped.items():
                if current_key != storage_key:
                    if document is not None:
                        document.close()
                    source_path = _resolve_storage_key(paper_root, storage_key)
                    document = pymupdf.open(source_path)
                    current_key = storage_key
                markdown = _extract_regions(document, regions)
                if not markdown:
                    if overwrite:
                        conn.execute(
                            "DELETE FROM answer_versions WHERE answer_id = ? AND version = 1 AND language = 'en'",
                            (answer_id,),
                        )
                        conn.execute("UPDATE answers SET status = 'source_only' WHERE id = ?", (answer_id,))
                    empty += 1
                    continue
                if overwrite:
                    conn.execute(
                        "DELETE FROM answer_versions WHERE answer_id = ? AND version = 1 AND language = 'en'",
                        (answer_id,),
                    )
                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO answer_versions (
                        answer_id, version, language, raw_text, markdown, status
                    ) VALUES (?, 1, 'en', ?, ?, 'draft')
                    """,
                    (answer_id, markdown, markdown),
                )
                if cursor.rowcount:
                    written += 1
                    conn.execute("UPDATE answers SET status = 'draft' WHERE id = ?", (answer_id,))
            conn.commit()
        finally:
            if document is not None:
                document.close()
        return AnswerExtractionSummary(seen, written, empty)


def _resolve_storage_key(paper_root: Path, storage_key: str) -> Path:
    relative = Path(storage_key)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"invalid storage key: {storage_key}")
    path = (paper_root / relative).resolve()
    if not path.is_relative_to(paper_root) or not path.is_file():
        raise ValueError(f"answer PDF does not exist: {storage_key}")
    return path


def _extract_regions(document: pymupdf.Document, regions: list[sqlite3.Row]) -> str:
    parts: list[str] = []
    for region in regions:
        page_index = int(region["page_index"])
        if page_index < 0 or page_index >= document.page_count:
            raise ValueError(f"answer crop page is outside source PDF: {page_index}")
        page = document[page_index]
        clip = _clip_rect(region).intersect(page.rect)
        if clip.is_empty or clip.is_infinite:
            raise ValueError(f"invalid answer crop rectangle on page {page_index}")
        text = _normalize_markdown_text(page.get_text("text", clip=clip, sort=True))
        if _looks_garbled(text):
            return ""
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _clip_rect(region: sqlite3.Row) -> pymupdf.Rect:
    clip = pymupdf.Rect(
        float(region["x0"]),
        float(region["y0"]),
        float(region["x1"]),
        float(region["y1"]),
    )
    dpi = region["render_dpi"]
    post_values = tuple(region[key] for key in ("post_left", "post_top", "post_right", "post_bottom"))
    if dpi and all(value is not None for value in post_values):
        left, top, right, bottom = (float(value) for value in post_values)
        scale = 72.0 / float(dpi)
        clip = pymupdf.Rect(
            clip.x0 + left * scale,
            clip.y0 + top * scale,
            clip.x0 + right * scale,
            clip.y0 + bottom * scale,
        )
    return clip


def _normalize_markdown_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.split("\n")]
    lines = [line for line in lines if not any(pattern.match(line) for pattern in BOILERPLATE_LINES)]
    compact: list[str] = []
    for line in lines:
        if line:
            compact.append(line)
        elif compact and compact[-1] != "":
            compact.append("")
    return "\n".join(compact).strip()


def _looks_garbled(value: str) -> bool:
    meaningful = [character for character in value if not character.isspace()]
    if not meaningful:
        return False
    suspicious = 0
    for character in meaningful:
        codepoint = ord(character)
        if (
            0x7F <= codepoint <= 0x9F
            or 0xE000 <= codepoint <= 0xF8FF
            or 0x0400 <= codepoint <= 0x052F
            or 0x0590 <= codepoint <= 0x08FF
            or 0x0B80 <= codepoint <= 0x0BFF
            or 0x1000 <= codepoint <= 0x109F
            or 0x1200 <= codepoint <= 0x137F
        ):
            return True
        if character in {"□", "�", "¦", "¸", "¶"}:
            suspicious += 1
    return suspicious > 0 and suspicious / len(meaningful) >= 0.005
