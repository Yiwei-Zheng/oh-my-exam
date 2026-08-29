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


@dataclass(frozen=True)
class Invitation:
    id: int
    code_hint: str
    role: str
    max_uses: int
    used_count: int
    expires_at: str
    is_active: bool
    created_at: str

    def as_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "code_hint": self.code_hint,
            "role": self.role,
            "max_uses": self.max_uses,
            "used_count": self.used_count,
            "expires_at": self.expires_at,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


class DuplicateUserError(Exception):
    pass


class InvalidUserError(Exception):
    pass


class InvalidInvitationError(Exception):
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

    def create_invitation(
        self,
        created_by: int,
        role: str,
        max_uses: int,
        expires_in_days: int,
    ) -> tuple[Invitation, str]:
        if role not in ROLES:
            raise InvalidInvitationError("invalid_role")
        if not 1 <= max_uses <= 100:
            raise InvalidInvitationError("invalid_max_uses")
        if not 1 <= expires_in_days <= 365:
            raise InvalidInvitationError("invalid_expiry")
        raw = secrets.token_hex(9).upper()
        code = f"OME-{raw[:6]}-{raw[6:12]}-{raw[12:]}"
        expires_at = (datetime.now(timezone.utc) + timedelta(days=expires_in_days)).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO invitations (
                    code_hash, code_hint, role, max_uses, expires_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (self._invitation_hash(code), code[-6:], role, max_uses, expires_at, created_by),
            )
            row = connection.execute(
                "SELECT * FROM invitations WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        return self._invitation(row), code

    def list_invitations(self) -> list[Invitation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM invitations ORDER BY created_at DESC, id DESC"
            ).fetchall()
        return [self._invitation(row) for row in rows]

    def revoke_invitation(self, invitation_id: int) -> Invitation | None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE invitations SET is_active = 0 WHERE id = ?", (invitation_id,)
            )
            row = connection.execute(
                "SELECT * FROM invitations WHERE id = ?", (invitation_id,)
            ).fetchone()
        return None if row is None else self._invitation(row)

    def register_with_invitation(self, email: str, password: str, code: str) -> User:
        normalized = email.strip().lower()
        if "@" not in normalized or len(normalized) > 254:
            raise InvalidUserError("invalid_email")
        if len(password) < 15:
            raise InvalidUserError("password_too_short")
        now = self._now()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                row = connection.execute(
                    """
                    SELECT * FROM invitations
                    WHERE code_hash = ? AND is_active = 1
                      AND used_count < max_uses AND expires_at > ?
                    """,
                    (self._invitation_hash(code), now),
                ).fetchone()
                if row is None:
                    raise InvalidInvitationError("invalid_or_expired_invitation")
                cursor = connection.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES (?, ?, ?)",
                    (normalized, self.passwords.hash(password), row["role"]),
                )
                connection.execute(
                    "UPDATE invitations SET used_count = used_count + 1 WHERE id = ?",
                    (row["id"],),
                )
                user_row = connection.execute(
                    "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
                ).fetchone()
        except sqlite3.IntegrityError as exc:
            raise DuplicateUserError("email_already_exists") from exc
        return self._user(user_row)

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
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY,
                    code_hash TEXT NOT NULL UNIQUE,
                    code_hint TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('student', 'teacher', 'admin')),
                    max_uses INTEGER NOT NULL DEFAULT 1 CHECK (max_uses BETWEEN 1 AND 100),
                    used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0),
                    expires_at TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
                    created_by INTEGER NOT NULL REFERENCES users(id),
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE INDEX IF NOT EXISTS idx_invitations_active_expiry
                    ON invitations(is_active, expires_at);
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
    def _invitation(row: sqlite3.Row) -> Invitation:
        return Invitation(
            id=int(row["id"]), code_hint=str(row["code_hint"]), role=str(row["role"]),
            max_uses=int(row["max_uses"]), used_count=int(row["used_count"]),
            expires_at=str(row["expires_at"]), is_active=bool(row["is_active"]),
            created_at=str(row["created_at"]),
        )

    @staticmethod
    def _invitation_hash(code: str) -> str:
        return hashlib.sha256(code.strip().upper().encode()).hexdigest()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
