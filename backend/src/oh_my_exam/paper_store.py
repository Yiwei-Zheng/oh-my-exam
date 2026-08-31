from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import pymupdf


class PaperNotFoundError(LookupError):
    pass


class FileSystemPaperStore:
    """Development paper store backed by data/raw_papers.

    Production storage will implement the same lookup boundary with an S3-compatible
    object store. The API never accepts an upstream URL or an arbitrary path.
    """

    def __init__(self, paper_root: Path) -> None:
        self.paper_root = paper_root.resolve()

    def find_by_storage_key(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if not storage_key or relative.is_absolute() or ".." in relative.parts:
            raise PaperNotFoundError("invalid paper storage key")
        path = (self.paper_root / relative).resolve()
        if not path.is_relative_to(self.paper_root) or not path.is_file():
            raise PaperNotFoundError(f"paper not found: {storage_key}")
        return path

    def render_marked_page(
        self, storage_key: str, regions: Sequence[Mapping[str, object]], *, dpi: int = 144
    ) -> tuple[bytes, int]:
        if not regions:
            raise PaperNotFoundError("question has no source region")
        page_index = int(regions[0]["page_index"])
        try:
            with pymupdf.open(self.find_by_storage_key(storage_key)) as document:
                page = document[page_index]
                for region in regions:
                    if int(region["page_index"]) != page_index:
                        continue
                    rect = pymupdf.Rect(*(float(region[key]) for key in ("x0", "y0", "x1", "y1"))) & page.rect
                    page.draw_rect(
                        rect,
                        color=(0.96, 0.45, 0.05),
                        fill=(1, 0.78, 0.08),
                        fill_opacity=0.14,
                        width=2,
                    )
                return page.get_pixmap(dpi=dpi, alpha=False).tobytes("jpeg", jpg_quality=88), page_index
        except (IndexError, ValueError, pymupdf.FileDataError) as exc:
            raise PaperNotFoundError(f"source page could not be rendered: {storage_key}") from exc
