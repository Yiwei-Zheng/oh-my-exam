from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
SHARED_SRC = ROOT / "tools" / "shared" / "cie" / "src"
TOOL_SRC = ROOT / "tools" / "splitters" / "alevel" / "cie" / "src" / "common"

if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))
if str(TOOL_SRC) not in sys.path:
    sys.path.insert(0, str(TOOL_SRC))

from cie_alevel_splitter.cli import main


if __name__ == "__main__":
    main()
