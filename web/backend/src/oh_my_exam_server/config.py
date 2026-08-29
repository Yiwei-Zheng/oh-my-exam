from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_path: Path
    paper_root: Path
    cors_origins: tuple[str, ...] = ()

    @classmethod
    def from_env(cls) -> "Settings":
        default_project_root = Path(__file__).resolve().parents[4]
        project_root = Path(os.environ.get("OME_PROJECT_ROOT", default_project_root)).resolve()
        database_path = Path(
            os.environ.get(
                "OME_DATABASE_PATH",
                project_root / "data" / "databases" / "global_exam_catalog.sqlite",
            )
        ).resolve()
        paper_root = Path(
            os.environ.get("OME_PAPER_ROOT", project_root / "data" / "raw_papers")
        ).resolve()
        origins = tuple(
            origin.strip()
            for origin in os.environ.get("OME_CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
        return cls(project_root, database_path, paper_root, origins)
