from __future__ import annotations

from pathlib import Path
import re


class PaperNotFoundError(LookupError):
    pass


class FileSystemPaperStore:
    """Development paper store backed by data/raw_papers.

    Production storage will implement the same lookup boundary with an S3-compatible
    object store. The API never accepts an upstream URL or an arbitrary path.
    """

    def __init__(self, paper_root: Path) -> None:
        self.paper_root = paper_root.resolve()

    def find_by_stem(self, stem: str) -> Path:
        if not stem or Path(stem).name != stem or re.fullmatch(r"[A-Za-z0-9_.-]+", stem) is None:
            raise PaperNotFoundError("invalid paper stem")
        matches = [path.resolve() for path in self.paper_root.rglob(f"{stem}.pdf") if path.is_file()]
        safe_matches = [path for path in matches if path.is_relative_to(self.paper_root)]
        if len(safe_matches) != 1:
            raise PaperNotFoundError(f"expected one local PDF for {stem}, found {len(safe_matches)}")
        return safe_matches[0]
