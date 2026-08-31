from __future__ import annotations

from pathlib import Path
from threading import Lock


class QuestionImageNotFoundError(LookupError):
    pass


class FileSystemQuestionImageStore:
    """Read pre-rendered question images through catalog-owned storage keys."""

    def __init__(self, image_root: Path) -> None:
        self.image_root = image_root.resolve()
        self._index: dict[str, Path | None] | None = None
        self._index_lock = Lock()

    def find_by_storage_key(self, storage_key: str) -> Path:
        relative = Path(storage_key)
        if not storage_key or relative.is_absolute() or ".." in relative.parts:
            raise QuestionImageNotFoundError("invalid question image storage key")
        path = (self.image_root / relative).resolve()
        if not path.is_relative_to(self.image_root) or not path.is_file():
            raise QuestionImageNotFoundError(f"question image not found: {storage_key}")
        return path

    def find_by_filename(self, filename: str) -> Path:
        if not filename or Path(filename).name != filename:
            raise QuestionImageNotFoundError("invalid question image filename")
        with self._index_lock:
            if self._index is None:
                index: dict[str, Path | None] = {}
                for path in self.image_root.rglob("*"):
                    if not path.is_file() or path.suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"}:
                        continue
                    key = path.name.casefold()
                    index[key] = None if key in index else path.resolve()
                self._index = index
            path = self._index.get(filename.casefold())
        if path is None:
            raise QuestionImageNotFoundError(f"question image not found: {filename}")
        return path
