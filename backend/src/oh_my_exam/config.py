from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys


@dataclass(frozen=True)
class Settings:
    project_root: Path
    database_path: Path
    paper_root: Path
    cors_origins: tuple[str, ...] = ()
    app_database_path: Path | None = None
    jwt_secret: str = ""
    secure_cookies: bool = False
    bootstrap_admin_email: str = ""
    bootstrap_admin_password: str = ""
    question_update_command: tuple[str, ...] = ()
    login_rate_limit_storage_uri: str = "memory://"

    @classmethod
    def from_env(cls) -> "Settings":
        backend_root = Path(__file__).resolve().parents[2]
        default_project_root = backend_root.parent
        project_root = Path(os.environ.get("OME_PROJECT_ROOT", default_project_root)).resolve()
        database_path = Path(
            os.environ.get(
                "OME_DATABASE_PATH",
                backend_root / "data" / "databases" / "global_exam_catalog.sqlite",
            )
        ).resolve()
        paper_root = Path(
            os.environ.get(
                "OME_PAPER_ROOT",
                backend_root / "data" / "raw_papers",
            )
        ).resolve()
        origins = tuple(
            origin.strip()
            for origin in os.environ.get("OME_CORS_ORIGINS", "").split(",")
            if origin.strip()
        )
        app_database_path = Path(
            os.environ.get(
                "OME_APP_DATABASE_PATH",
                backend_root / "data" / "application.sqlite3",
            )
        ).resolve()
        command_raw = os.environ.get("OME_QUESTION_UPDATE_COMMAND_JSON", "")
        command: tuple[str, ...] = (
            sys.executable,
            str(backend_root / "scripts" / "release_catalog.py"),
        )
        if command_raw:
            parsed = json.loads(command_raw)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("OME_QUESTION_UPDATE_COMMAND_JSON must be a JSON string array")
            command = tuple(parsed)
        return cls(
            project_root,
            database_path,
            paper_root,
            origins,
            app_database_path,
            os.environ.get("OME_JWT_SECRET", ""),
            os.environ.get("OME_SECURE_COOKIES", "").lower() in {"1", "true", "yes"},
            os.environ.get("OME_BOOTSTRAP_ADMIN_EMAIL", ""),
            os.environ.get("OME_BOOTSTRAP_ADMIN_PASSWORD", ""),
            command,
            os.environ.get("OME_LOGIN_RATE_LIMIT_STORAGE_URI", "memory://"),
        )
