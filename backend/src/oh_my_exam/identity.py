from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import sqlite3
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt


ROLES = {"student", "teacher", "admin"}
SESSION_COOKIE = "ome_session"


@dataclass(frozen=True)
class User:
    id: int
    email: str
    role: str
    is_active: bool
    created_at: str
    last_login_at: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }


class DuplicateUserError(Exception):
    pass


class InvalidUserError(Exception):
    pass


class IdentityStore:
    def __init__(self, database_path: Path, jwt_secret: str = "") -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.passwords = PasswordHasher()
        self._dummy_password_hash = self.passwords.hash(secrets.token_urlsafe(32))
        self.jwt_secret = jwt_secret or self._load_or_create_secret()
        self._migrate()

    def bootstrap_admin(self, email: str, password: str) -> None:
        if not email or not password:
            return
        normalized = self._normalize_email(email)
        with self._connect() as connection:
            exists = connection.execute("SELECT 1 FROM users WHERE email = ?", (normalized,)).fetchone()
            if exists:
                return
            connection.execute(
                "INSERT INTO users (email, password_hash, role) VALUES (?, ?, 'admin')",
                (normalized, self.passwords.hash(password)),
            )

    def create_user(self, email: str, password: str, role: str) -> User:
        normalized = email.strip().lower()
        if "@" not in normalized or len(normalized) > 254:
            raise InvalidUserError("invalid_email")
        if role not in ROLES:
            raise InvalidUserError("invalid_role")
        if len(password) < 15:
            raise InvalidUserError("password_too_short")
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                    (normalized, self.passwords.hash(password), role),
                )
                row = connection.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError("email_already_exists") from exc
        return self._user(row)

    def list_users(self) -> list[User]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._user(row) for row in rows]

    def authenticate(self, email: str, password: str) -> User | None:
        normalized = self._normalize_email(email)
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
            try:
                valid = self.passwords.verify(
                    self._dummy_password_hash if row is None else row["password_hash"],
                    password,
                )
            except VerifyMismatchError:
                return None
            if row is None or not row["is_active"] or not valid:
                return None
            now = self._now()
            connection.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"]))
            connection.execute(
                "INSERT INTO activity_events (user_id, event_type, occurred_at) VALUES (?, 'login', ?)",
                (row["id"], now),
            )
            refreshed = connection.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
        return self._user(refreshed)

    def issue_session(self, user: User) -> str:
        now = datetime.now(timezone.utc)
        return jwt.encode(
            {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(hours=12)},
            self.jwt_secret,
            algorithm="HS256",
        )

    def user_from_session(self, token: str | None) -> User | None:
        if not token:
            return None
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=["HS256"])
            user_id = int(payload["sub"])
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ? AND is_active = 1", (user_id,)).fetchone()
        return None if row is None else self._user(row)

    def dashboard_statistics(self) -> dict[str, object]:
        with self._connect() as connection:
            total = int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])
            active = int(connection.execute(
                "SELECT COUNT(DISTINCT user_id) FROM activity_events WHERE occurred_at >= datetime('now', '-7 days')"
            ).fetchone()[0])
            roles = {row["role"]: int(row["count"]) for row in connection.execute(
                "SELECT role, COUNT(*) AS count FROM users GROUP BY role"
            )}
            activity_rows = connection.execute(
                """
                WITH RECURSIVE days(day) AS (
                    SELECT date('now', '-13 days') UNION ALL
                    SELECT date(day, '+1 day') FROM days WHERE day < date('now')
                )
                SELECT days.day, COUNT(activity_events.id) AS count
                FROM days LEFT JOIN activity_events ON date(activity_events.occurred_at) = days.day
                GROUP BY days.day ORDER BY days.day
                """
            ).fetchall()
        return {
            "users_total": total,
            "active_7d": active,
            "roles": {role: roles.get(role, 0) for role in sorted(ROLES)},
            "activity": [{"date": row["day"], "count": int(row["count"])} for row in activity_rows],
        }

    def _migrate(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT
                );
                CREATE TABLE IF NOT EXISTS activity_events (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_activity_events_time ON activity_events(occurred_at);
                CREATE INDEX IF NOT EXISTS idx_activity_events_user_time ON activity_events(user_id, occurred_at);
                """
            )

    def _load_or_create_secret(self) -> str:
        secret_path = self.database_path.with_suffix(".secret")
        if secret_path.is_file():
            return secret_path.read_text(encoding="utf-8").strip()
        secret = secrets.token_urlsafe(48)
        secret_path.write_text(secret, encoding="utf-8")
        return secret

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _normalize_email(value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or len(normalized) > 254:
            return hashlib.sha256(normalized.encode()).hexdigest() + "@invalid.local"
        return normalized

    @staticmethod
    def _user(row: sqlite3.Row) -> User:
        return User(
            id=int(row["id"]), email=str(row["email"]), role=str(row["role"]),
            is_active=bool(row["is_active"]), created_at=str(row["created_at"]),
            last_login_at=None if row["last_login_at"] is None else str(row["last_login_at"]),
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
