from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    candidates = [current, *current.parents]
    for candidate in candidates:
        if (candidate / "docs" / "requirements.md").exists() and (candidate / "backend" / "pyproject.toml").exists():
            return candidate
    return Path.cwd().resolve()


def project_relative_path(path: Path, *, project_root: Path | None = None) -> str:
    root = (project_root or find_project_root(path)).resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
