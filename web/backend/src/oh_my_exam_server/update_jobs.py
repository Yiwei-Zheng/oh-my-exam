from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import subprocess
from threading import Lock, Thread
from typing import Sequence


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

    def start(self, requested_by: int) -> dict[str, object]:
        if not self.configured:
            raise RuntimeError("question update pipeline is not configured")
        with self._lock, self._connect() as connection:
            running = connection.execute(
                "SELECT * FROM question_update_jobs WHERE status = 'running' ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if running is not None:
                return self._serialize(running)
            cursor = connection.execute(
                "INSERT INTO question_update_jobs (requested_by, status, stage, progress, message) VALUES (?, 'running', 'checking', 2, '正在检查来源')",
                (requested_by,),
            )
            job_id = int(cursor.lastrowid)
        Thread(target=self._run, args=(job_id,), daemon=True, name=f"question-update-{job_id}").start()
        return self.get(job_id)

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

    def _run(self, job_id: int) -> None:
        try:
            process = subprocess.Popen(
                self.command,
                cwd=self.database_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self._consume_progress(job_id, line.strip())
            code = process.wait()
            if code:
                raise RuntimeError(f"题库更新进程退出，代码 {code}")
            self._update(job_id, status="completed", stage="completed", progress=100, message="题库已更新")
        except Exception as exc:
            self._update(job_id, status="failed", stage="failed", message=str(exc)[:500])

    def _consume_progress(self, job_id: int, line: str) -> None:
        if not line:
            return
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            self._update(job_id, message=line[:500])
            return
        if not isinstance(payload, dict):
            return
        allowed_stages = {"checking", "downloading", "splitting", "cataloging", "classifying"}
        stage = str(payload.get("stage", ""))
        progress = payload.get("progress")
        self._update(
            job_id,
            stage=stage if stage in allowed_stages else None,
            progress=max(0, min(99, int(progress))) if isinstance(progress, (int, float)) else None,
            message=str(payload.get("message", ""))[:500] or None,
        )

    def _update(
        self,
        job_id: int,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: int | None = None,
        message: str | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[object] = []
        for name, value in (("status", status), ("stage", stage), ("progress", progress), ("message", message)):
            if value is not None:
                fields.append(f"{name} = ?")
                values.append(value)
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
                    started_at TEXT NOT NULL DEFAULT (datetime('now')),
                    finished_at TEXT
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _serialize(row: sqlite3.Row) -> dict[str, object]:
        return {
            "id": int(row["id"]), "status": row["status"], "stage": row["stage"],
            "progress": int(row["progress"]), "message": row["message"],
            "started_at": row["started_at"], "finished_at": row["finished_at"],
        }
