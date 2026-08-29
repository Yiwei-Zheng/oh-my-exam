from __future__ import annotations

from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = BACKEND_ROOT / "data"
DATABASE_ROOT = DATA_ROOT / "databases"
RAW_PAPER_ROOT = DATA_ROOT / "raw_papers"
CONFIG_ROOT = BACKEND_ROOT / "config"
RESOURCE_ROOT = BACKEND_ROOT / "resources"
