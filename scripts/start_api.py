#!/usr/bin/env python3
"""Start the Oh My Exam API for local development."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SOURCE = PROJECT_ROOT / "backend" / "src"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Oh My Exam API."
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("WEB_CONCURRENCY", "1")))
    parser.add_argument("--check", action="store_true", help="Validate runtime files without starting.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not BACKEND_SOURCE.is_dir():
        raise SystemExit("Backend source not found / 未找到后端源码")

    sys.path.insert(0, str(BACKEND_SOURCE))
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit("uvicorn is not installed / 当前环境未安装 uvicorn") from exc

    if args.check:
        print("[OK] Web server is ready / Web 服务器已就绪")
        return

    os.environ.setdefault("OME_PROJECT_ROOT", str(PROJECT_ROOT))
    uvicorn.run(
        "oh_my_exam.main:app",
        host=args.host,
        port=args.port,
        workers=max(1, args.workers),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
