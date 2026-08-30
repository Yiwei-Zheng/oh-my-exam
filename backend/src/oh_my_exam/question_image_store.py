from __future__ import annotations

from pathlib import Path


class QuestionImageNotFoundError(LookupError):
    pass


class FileSystemQuestionImageStore:
    """Read pre-rendered question images through catalog-owned storage keys."""

    def __init__(self, image_root: Path) -> None:
        self.image_root = image_root.resolve()

    def find_by_storage_key(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if not storage_key or relative.is_absolute() or ".." in relative.parts:
            raise QuestionImageNotFoundError("invalid question image storage key")
        path = (self.image_root / relative).resolve()
        if not path.is_relative_to(self.image_root) or not path.is_file():
            raise QuestionImageNotFoundError(f"question image not found: {storage_key}")
        return path
