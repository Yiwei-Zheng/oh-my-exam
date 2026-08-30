#!/usr/bin/env python3
"""Start the Oh My Exam frontend and backend together."""

from __future__ import annotations

from pathlib import Path
import sys


SCRIPTS_ROOT = Path(__file__).resolve().parent / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

from start_dev import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
