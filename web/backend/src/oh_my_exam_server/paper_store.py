from __future__ import annotations

from pathlib import Path


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
