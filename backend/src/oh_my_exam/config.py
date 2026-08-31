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
    question_image_root: Path | None = None

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
        question_image_root = Path(
            os.environ.get(
                "OME_QUESTION_IMAGE_ROOT",
                backend_root / "data" / "processed_questions",
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
            str(backend_root / "scripts" / "update_catalog.py"),
        )
        if command_raw:
            parsed = json.loads(command_raw)
            if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
                raise ValueError("OME_QUESTION_UPDATE_COMMAND_JSON must be a JSON string array")
            command = tuple(parsed)
        return cls(
            project_root=project_root,
            database_path=database_path,
            paper_root=paper_root,
            cors_origins=origins,
            app_database_path=app_database_path,
            jwt_secret=os.environ.get("OME_JWT_SECRET", ""),
            secure_cookies=os.environ.get("OME_SECURE_COOKIES", "").lower() in {"1", "true", "yes"},
            bootstrap_admin_email=os.environ.get("OME_BOOTSTRAP_ADMIN_EMAIL", ""),
            bootstrap_admin_password=os.environ.get("OME_BOOTSTRAP_ADMIN_PASSWORD", ""),
            question_update_command=command,
            login_rate_limit_storage_uri=os.environ.get("OME_LOGIN_RATE_LIMIT_STORAGE_URI", "memory://"),
            question_image_root=question_image_root,
        )
