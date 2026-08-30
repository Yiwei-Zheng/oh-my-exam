from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import threading
import time

import psutil


_SKIP_DIRECTORIES = {
    ".git",
    ".next",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "tmp",
}


@dataclass(frozen=True)
class StorageRoots:
    project: Path
    data: Path
    papers: Path
    databases: tuple[Path, ...]


class SystemMonitor:
    """Return host utilization and a cached project storage inventory."""

    def __init__(
        self,
        project_root: Path,
        paper_root: Path,
        database_paths: tuple[Path, ...],
        *,
        storage_cache_seconds: float = 30.0,
    ) -> None:
        project = project_root.resolve()
        self.roots = StorageRoots(
            project=project,
            data=(project / "backend" / "data").resolve(),
            papers=paper_root.resolve(),
            databases=tuple(path.resolve() for path in database_paths),
        )
        self.storage_cache_seconds = storage_cache_seconds
        self._storage_cache: dict[str, object] | None = None
        self._storage_cache_at = 0.0
        self._lock = threading.Lock()
        psutil.cpu_percent(interval=None)

    def snapshot(self) -> dict[str, object]:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(self.roots.project))
        return {
            "sampled_at": time.time(),
            "cpu": {"percent": round(psutil.cpu_percent(interval=None), 1)},
            "memory": {
                "percent": round(memory.percent, 1),
                "used_bytes": int(memory.used),
                "total_bytes": int(memory.total),
            },
            "disk": {
                "percent": round(disk.percent, 1),
                "used_bytes": int(disk.used),
                "total_bytes": int(disk.total),
                "free_bytes": int(disk.free),
            },
            "storage": self._storage_inventory(),
        }

    def _storage_inventory(self) -> dict[str, object]:
        now = time.monotonic()
        with self._lock:
            if (
                self._storage_cache is not None
                and now - self._storage_cache_at < self.storage_cache_seconds
            ):
                return self._storage_cache
            categories = {"code": 0, "databases": 0, "papers": 0, "other_data": 0}
            for path, size in _walk_files(self.roots.project):
                categories[self._category(path)] += size
            result: dict[str, object] = {
                "project_bytes": sum(categories.values()),
                "categories": categories,
            }
            self._storage_cache = result
            self._storage_cache_at = now
            return result

    def _category(self, path: Path) -> str:
        if _is_inside(path, self.roots.papers):
            return "papers"
        if any(path == database or _is_inside(path, database.parent) for database in self.roots.databases):
            if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"} or ".sqlite" in path.name:
                return "databases"
        if _is_inside(path, self.roots.data):
            return "other_data"
        return "code"


def _walk_files(root: Path):
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = os.scandir(directory)
        except OSError:
            continue
        with entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name not in _SKIP_DIRECTORIES:
                        stack.append(Path(entry.path))
                    continue
                try:
                    yield Path(entry.path).resolve(), entry.stat(follow_symlinks=False).st_size
                except OSError:
                    continue


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
