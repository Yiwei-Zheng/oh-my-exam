#!/usr/bin/env python3
"""Build and start the self-contained Oh My Exam web deployment."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


WEB_ROOT = Path(__file__).resolve().parent
BACKEND_SOURCE = WEB_ROOT / "backend" / "src"
FRONTEND_ROOT = WEB_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_ROOT / "dist"


def build_frontend(*, install: bool) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm is required to build the frontend / 构建前端需要 npm")
    if install:
        subprocess.run([npm, "ci"], cwd=FRONTEND_ROOT, check=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND_ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start Oh My Exam for Linux or local production use."
    )
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    parser.add_argument("--workers", type=int, default=int(os.environ.get("WEB_CONCURRENCY", "1")))
    parser.add_argument("--build", action="store_true", help="Build the frontend before starting.")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Run npm ci before building; implies --build.",
    )
    parser.add_argument("--check", action="store_true", help="Validate files without starting.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.install or args.build:
        build_frontend(install=args.install)
    if not FRONTEND_DIST.joinpath("index.html").is_file():
        raise SystemExit(
            "Frontend build not found. Run: python web/start.py --install\n"
            "未找到前端构建，请运行：python web/start.py --install"
        )
    if not BACKEND_SOURCE.is_dir():
        raise SystemExit("Backend source not found / 未找到后端源码")
    if args.check:
        print("[OK] Web deployment is ready / Web 部署文件已就绪")
        return

    sys.path.insert(0, str(BACKEND_SOURCE))
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "Backend dependencies are missing. Run: pip install -e web/backend"
        ) from exc

    os.environ.setdefault("OME_WEB_ROOT", str(WEB_ROOT))
    uvicorn.run(
        "oh_my_exam_server.main:app",
        host=args.host,
        port=args.port,
        workers=max(1, args.workers),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
