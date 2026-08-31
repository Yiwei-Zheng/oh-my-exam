from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from threading import Lock, Thread
from typing import Sequence


WORKFLOWS: tuple[dict[str, str], ...] = (
    {"id": "cie:9709", "code": "9709", "name": "Mathematics", "family": "CIE A-Level"},
    {"id": "cie:9231", "code": "9231", "name": "Mathematics - Further", "family": "CIE A-Level"},
    {"id": "ocr:step", "code": "STEP", "name": "Sixth Term Examination Paper", "family": "Admissions"},
    {"id": "uat:engaa", "code": "ENGAA", "name": "Engineering Admissions Assessment", "family": "UAT-UK"},
    {"id": "uat:nsaa", "code": "NSAA", "name": "Natural Sciences Admissions Assessment", "family": "UAT-UK"},
    {"id": "uat:tmua", "code": "TMUA", "name": "Test of Mathematics for University Admission", "family": "UAT-UK"},
)
WORKFLOW_IDS = {str(item["id"]) for item in WORKFLOWS}
UPDATE_STAGES = {"all", "download", "split", "inventory", "search"}
UPDATE_MODES = {"update", "overwrite"}
JOB_STAGE = {
    "all": "checking",
    "download": "downloading",
    "split": "splitting",
    "inventory": "cataloging",
    "search": "classifying",
}
STAGE_ORDER = {"checking": 0, "downloading": 1, "splitting": 2, "cataloging": 3, "classifying": 4}
MAX_PIPELINE_WORKERS = 32


class UpdateJobManager:
    """Runs one configured question-bank pipeline at a time without invoking a shell."""

    def __init__(self, database_path: Path, command: Sequence[str]) -> None:
        self.database_path = database_path.resolve()
        self.command = tuple(command)
        self._lock = Lock()
        self._migrate()
        with self._connect() as connection:
            connection.execute(
                "UPDATE question_update_jobs SET status = 'failed', message = '服务重启，任务已中断' WHERE status = 'running'"
            )

    @property
    def configured(self) -> bool:
        return bool(self.command)

    @property
    def recommended_concurrency(self) -> int:
        return min(MAX_PIPELINE_WORKERS, max(4, os.cpu_count() or 4))

    def workflows(self) -> list[dict[str, object]]:
        return [{**item, "status": "ready"} for item in WORKFLOWS]

    def probe(self, subject_ids: Sequence[str], paper_root: Path) -> dict[str, object]:
        selected = self._validate_subjects(subject_ids)
        resources: list[dict[str, object]] = []
        errors: list[dict[str, str]] = []
        for subject_id in selected:
            try:
                if subject_id.startswith("cie:"):
                    resources.extend(self._probe_cie([subject_id], paper_root))
                elif subject_id == "ocr:step":
                    resources.extend(self._probe_step(paper_root))
                else:
                    resources.extend(self._probe_uat(subject_id, paper_root))
            except Exception as exc:
                errors.append({"subject_id": subject_id, "message": str(exc)[:500]})
        new_resources = [item for item in resources if not item["local"]]
        return {
            "subjects": selected,
            "resource_count": len(resources),
            "local_count": len(resources) - len(new_resources),
            "new_count": len(new_resources),
            "new_resources": new_resources,
            "errors": errors,
            "probed_at": datetime.now(timezone.utc).isoformat(),
        }

    def start_probe(
        self,
        requested_by: int,
        subject_ids: Sequence[str],
        paper_root: Path,
    ) -> dict[str, object]:
        selected = self._validate_subjects(subject_ids)
        job_id, existing = self._create_job(requested_by, "probe", "checking", "正在嗅探来源")
        if existing is not None:
            return existing
        Thread(
            target=self._run_probe,
            args=(job_id, selected, paper_root),
            daemon=True,
            name=f"question-update-probe-{job_id}",
        ).start()
        return self.get(job_id)

    def start(
        self,
        requested_by: int,
        subject_ids: Sequence[str] | None = None,
        concurrency: int | None = None,
        stage: str = "all",
        mode: str = "update",
    ) -> dict[str, object]:
        if not self.configured:
            raise RuntimeError("question update pipeline is not configured")
        selected = self._validate_subjects(subject_ids or tuple(WORKFLOW_IDS))
        concurrency = max(1, min(MAX_PIPELINE_WORKERS, int(concurrency or self.recommended_concurrency)))
        if stage not in UPDATE_STAGES:
            raise ValueError(f"unknown_update_stage: {stage}")
        if mode not in UPDATE_MODES:
            raise ValueError(f"unknown_update_mode: {mode}")
        job_id, existing = self._create_job(
            requested_by,
            stage,
            JOB_STAGE[stage],
            "正在执行完整流水线" if stage == "all" else f"正在执行 {stage} 阶段",
        )
        if existing is not None:
            return existing
        Thread(
            target=self._run,
            args=(job_id, selected, concurrency, stage, mode),
            daemon=True,
            name=f"question-update-{job_id}",
        ).start()
        return self.get(job_id)

    def _create_job(
        self,
        requested_by: int,
        action: str,
        stage: str,
        message: str,
    ) -> tuple[int, dict[str, object] | None]:
        with self._lock, self._connect() as connection:
            running = connection.execute(
                "SELECT * FROM question_update_jobs WHERE status = 'running' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if running is not None:
                return int(running["id"]), self._serialize(running)
            cursor = connection.execute(
                """
                INSERT INTO question_update_jobs
                    (requested_by, status, stage, action, progress, message)
                VALUES (?, 'running', ?, ?, 2, ?)
                """,
                (requested_by, stage, action, message),
            )
            return int(cursor.lastrowid), None

    def latest(self) -> dict[str, object] | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM question_update_jobs ORDER BY id DESC LIMIT 1").fetchone()
        return None if row is None else self._serialize(row)

    def get(self, job_id: int) -> dict[str, object]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM question_update_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise LookupError(f"update job not found: {job_id}")
        return self._serialize(row)

    def _run_probe(self, job_id: int, subject_ids: Sequence[str], paper_root: Path) -> None:
        try:
            result = self.probe(subject_ids, paper_root)
            self._update(
                job_id,
                status="completed",
                stage="checking",
                progress=100,
                message="资源嗅探完成",
                result=result,
            )
        except Exception as exc:
            self._update(job_id, status="failed", stage="failed", message=str(exc)[:500])

    def _run(
        self,
        job_id: int,
        subject_ids: Sequence[str],
        concurrency: int,
        stage: str,
        mode: str,
    ) -> None:
        try:
            environment = os.environ.copy()
            environment["OME_UPDATE_SUBJECTS"] = ",".join(subject_ids)
            environment["OME_UPDATE_CONCURRENCY"] = str(concurrency)
            environment["OME_UPDATE_STAGE"] = stage
            environment["OME_UPDATE_MODE"] = mode
            environment["PYTHONUTF8"] = "1"
            environment["PYTHONIOENCODING"] = "utf-8"
            process = subprocess.Popen(
                self.command,
                cwd=self.database_path.parent,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="strict",
                shell=False,
            )
            assert process.stdout is not None
            last_message = ""
            for line in process.stdout:
                last_message = self._consume_progress(job_id, line.strip()) or last_message
            code = process.wait()
            if code:
                raise RuntimeError(f"题库更新进程退出，代码 {code}")
            self._update(job_id, status="completed", stage="completed", progress=100, message=last_message or "题库已更新")
        except Exception as exc:
            self._update(job_id, status="failed", stage="failed", message=str(exc)[:500])

    @staticmethod
    def _validate_subjects(subject_ids: Sequence[str]) -> list[str]:
        selected = list(dict.fromkeys(str(item) for item in subject_ids))
        if not selected:
            raise ValueError("select_at_least_one_subject")
        unknown = sorted(set(selected) - WORKFLOW_IDS)
        if unknown:
            raise ValueError(f"unknown_update_subjects: {', '.join(unknown)}")
        return selected

    @staticmethod
    def _probe_cie(subject_ids: Sequence[str], paper_root: Path) -> list[dict[str, object]]:
        from datetime import date

        from .pipelines.adapters.cie_alevel.downloader.frank_discovery import discover_frank_assets

        codes = {subject_id.split(":", 1)[1] for subject_id in subject_ids}
        assets = discover_frank_assets(
            qualification="a_level",
            subject_codes=codes,
            start_year=2020,
            end_year=date.today().year,
            seasons=("Mar", "Jun", "Nov"),
            workers=4,
        )
        if not assets:
            raise RuntimeError(f"Frank returned no resources for {', '.join(sorted(codes))}")
        return [
            {
                "id": asset.stem,
                "subject_id": f"cie:{asset.subject_code}",
                "label": asset.stem,
                "year": 2000 + int(asset.session[1:3]),
                "document_type": asset.document_type,
                "local": any(
                    (paper_root / path).is_file() and (paper_root / path).stat().st_size > 0
                    for path in (asset.relative_pdf_path, asset.legacy_relative_pdf_path)
                ),
            }
            for asset in assets
        ]

    @staticmethod
    def _probe_step(paper_root: Path) -> list[dict[str, object]]:
        from .pipelines.adapters.step.downloader.catalog import discover_assets

        return [
            {
                "id": asset.stem,
                "subject_id": "ocr:step",
                "label": asset.stem,
                "year": asset.year,
                "document_type": asset.document_type,
                "local": (paper_root / asset.relative_pdf_path).is_file()
                and (paper_root / asset.relative_pdf_path).stat().st_size > 0,
            }
            for asset in discover_assets()
        ]

    @staticmethod
    def _probe_uat(subject_id: str, paper_root: Path) -> list[dict[str, object]]:
        from .pipelines.adapters.uat.downloader.catalog import DEFAULT_ARCHIVE_URLS, discover_assets

        exam = subject_id.split(":", 1)[1]
        page = "tmua-preparation" if exam == "tmua" else "esat-preparation"
        archive_url = next(url for url in DEFAULT_ARCHIVE_URLS if page in url)
        assets = [asset for asset in discover_assets(archive_url) if asset.exam == exam]
        if not assets:
            raise RuntimeError(f"UAT-UK returned no resources for {exam}")
        return [
            {
                "id": asset.stem,
                "subject_id": subject_id,
                "label": asset.stem,
                "year": asset.year,
                "document_type": asset.document_type,
                "local": (paper_root / asset.relative_pdf_path).is_file()
                and (paper_root / asset.relative_pdf_path).stat().st_size > 0,
            }
            for asset in assets
        ]

    def _consume_progress(self, job_id: int, line: str) -> str | None:
        if not line:
            return None
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            self._update(job_id, message=line[:500])
            return line[:500]
        if not isinstance(payload, dict):
            return None
        allowed_stages = {"checking", "downloading", "splitting", "cataloging", "classifying"}
        stage = str(payload.get("stage", ""))
        progress = payload.get("progress")
        current = self.get(job_id)
        if stage in allowed_stages and STAGE_ORDER[stage] < STAGE_ORDER.get(str(current["stage"]), 0):
            stage = ""
        self._update(
            job_id,
            stage=stage if stage in allowed_stages else None,
            progress=max(int(current["progress"]), min(99, int(progress)))
            if isinstance(progress, (int, float))
            else None,
            message=str(payload.get("message", ""))[:500] or None,
        )
        return str(payload.get("message", ""))[:500] or None

    def _update(
        self,
        job_id: int,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        message: str | None = None,
        result: dict[str, object] | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[object] = []
        for name, value in (("status", status), ("stage", stage), ("progress", progress), ("message", message)):
            if value is not None:
                fields.append(f"{name} = ?")
                values.append(value)
        if result is not None:
            fields.append("result_json = ?")
            values.append(json.dumps(result, ensure_ascii=False))
        if status in {"completed", "failed"}:
            fields.append("finished_at = ?")
            values.append(datetime.now(timezone.utc).isoformat())
        if not fields:
            return
        values.append(job_id)
        with self._connect() as connection:
            connection.execute(f"UPDATE question_update_jobs SET {', '.join(fields)} WHERE id = ?", values)

    def _migrate(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS question_update_jobs (
                    id INTEGER PRIMARY KEY,
                    requested_by INTEGER NOT NULL REFERENCES users(id),
                    status TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed')),
                    stage TEXT NOT NULL,
                    progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
                    message TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL DEFAULT 'all',
                    result_json TEXT,
                    started_at TEXT NOT NULL DEFAULT (datetime('now')),
                    finished_at TEXT
                )
                """
            )
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(question_update_jobs)")}
            if "action" not in columns:
                connection.execute("ALTER TABLE question_update_jobs ADD COLUMN action TEXT NOT NULL DEFAULT 'all'")
            if "result_json" not in columns:
                connection.execute("ALTER TABLE question_update_jobs ADD COLUMN result_json TEXT")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, object]:
        result = json.loads(row["result_json"]) if row["result_json"] else None
        started_at = datetime.fromisoformat(row["started_at"])
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        finished_at = datetime.fromisoformat(row["finished_at"]) if row["finished_at"] else None
        if finished_at is not None and finished_at.tzinfo is None:
            finished_at = finished_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = max(0, round(((finished_at or datetime.now(timezone.utc)) - started_at).total_seconds()))
        progress = int(row["progress"])
        eta_seconds = None
        if row["status"] == "running" and 5 <= progress < 100:
            eta_seconds = max(0, round(elapsed_seconds * (100 - progress) / progress))
        return {
            "id": int(row["id"]), "status": row["status"], "stage": row["stage"],
            "action": row["action"], "result": result,
            "progress": progress, "message": row["message"],
            "started_at": row["started_at"], "finished_at": row["finished_at"],
            "elapsed_seconds": elapsed_seconds, "eta_seconds": eta_seconds,
        }
