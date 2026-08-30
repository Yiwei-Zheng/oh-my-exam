from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3


@dataclass(frozen=True)
class AiUsageRecord:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_microusd: int
    operation: str = "unspecified"


class AiUsageStore:
    """Append-only AI usage ledger using booked, not estimated, costs."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._migrate()

    def record(self, usage: AiUsageRecord, *, user_id: int | None = None) -> None:
        if min(usage.input_tokens, usage.output_tokens, usage.cost_microusd) < 0:
            raise ValueError("AI usage values cannot be negative")
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO ai_usage_events (
                    provider, model, operation, input_tokens, output_tokens,
                    cost_microusd, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (usage.provider, usage.model, usage.operation, usage.input_tokens,
                 usage.output_tokens, usage.cost_microusd, user_id),
            )
            connection.commit()

    def monthly_bill(self, month: str | None = None) -> dict[str, object]:
        month = month or datetime.now(UTC).strftime("%Y-%m")
        try:
            datetime.strptime(month, "%Y-%m")
        except ValueError as exc:
            raise ValueError("month must use YYYY-MM format") from exc
        with closing(self._connect()) as connection:
            totals = connection.execute(
                """
                SELECT COUNT(*) AS calls,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(cost_microusd), 0) AS cost_microusd
                FROM ai_usage_events WHERE substr(occurred_at, 1, 7) = ?
                """, (month,),
            ).fetchone()
            rows = connection.execute(
                """
                SELECT provider, model, COUNT(*) AS calls,
                       SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens,
                       SUM(cost_microusd) AS cost_microusd
                FROM ai_usage_events WHERE substr(occurred_at, 1, 7) = ?
                GROUP BY provider, model
                ORDER BY cost_microusd DESC, provider, model
                """, (month,),
            ).fetchall()
        return {
            "month": month,
            "currency": "USD",
            "calls": int(totals["calls"]),
            "input_tokens": int(totals["input_tokens"]),
            "output_tokens": int(totals["output_tokens"]),
            "cost_microusd": int(totals["cost_microusd"]),
            "items": [dict(row) for row in rows],
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _migrate(self) -> None:
        with closing(self._connect()) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS ai_usage_events (
                    id INTEGER PRIMARY KEY,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL CHECK (input_tokens >= 0),
                    output_tokens INTEGER NOT NULL CHECK (output_tokens >= 0),
                    cost_microusd INTEGER NOT NULL CHECK (cost_microusd >= 0),
                    user_id INTEGER REFERENCES users(id),
                    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_ai_usage_events_time
                    ON ai_usage_events(occurred_at);
                """
            )
