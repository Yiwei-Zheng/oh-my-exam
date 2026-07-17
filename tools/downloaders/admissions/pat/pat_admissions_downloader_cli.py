from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = ROOT / "tools" / "downloaders" / "admissions" / "pat" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from pat_admissions_downloader.cli import main


if __name__ == "__main__":
    main()
