from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3


def migrate(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(answer_versions)")}
        if "raw_text" not in columns:
            connection.execute("ALTER TABLE answer_versions ADD COLUMN raw_text TEXT NOT NULL DEFAULT ''")
            connection.execute("UPDATE answer_versions SET raw_text = markdown WHERE raw_text = ''")

        marking_points = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'marking_points'"
        ).fetchone()
        if marking_points:
            count = int(connection.execute("SELECT COUNT(*) FROM marking_points").fetchone()[0])
            if count:
                raise RuntimeError("marking_points contains data; refusing to drop it automatically")
            connection.execute("DROP TABLE marking_points")

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"catalog integrity check failed: {integrity}")
        connection.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Upgrade the local catalog to the current clean-break schema.")
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    migrate(args.database.resolve())


if __name__ == "__main__":
    main()
