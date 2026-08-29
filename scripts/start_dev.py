#!/usr/bin/env python3
"""Start the API and Vite development server as one local process group."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
VENV_PYTHON = PROJECT_ROOT / ".venv" / (
    "Scripts/python.exe" if os.name == "nt" else "bin/python"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Oh My Exam API and frontend development server."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=4173)
    parser.add_argument(
        "--lan",
        action="store_true",
        help="Listen on all interfaces instead of localhost.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate dependencies and ports without starting either server.",
    )
    return parser.parse_args()


def require_runtime() -> str:
    if not VENV_PYTHON.is_file():
        raise RuntimeError(
            "Python environment not found. Run: python scripts/setup_env.py --group all"
        )
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm was not found on PATH. Install Node.js 20.17 or later.")
    if not (FRONTEND_ROOT / "node_modules").is_dir():
        raise RuntimeError("Frontend dependencies not found. Run: cd frontend && npm install")
    return npm


def require_available_port(port: int, label: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"{label} port {port} is already in use.") from exc


def process_options() -> dict[str, object]:
    if os.name == "nt":
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    return {"start_new_session": True}


def stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)


def validate_backend() -> None:
    subprocess.run(
        [str(VENV_PYTHON), str(PROJECT_ROOT / "scripts" / "start_api.py"), "--check"],
        cwd=PROJECT_ROOT,
        check=True,
        stdout=subprocess.DEVNULL,
    )


def main() -> int:
    args = parse_args()
    try:
        npm = require_runtime()
        require_available_port(args.api_port, "API")
        require_available_port(args.frontend_port, "Frontend")
        validate_backend()
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1

    if args.check:
        print("[OK] Frontend runtime and development ports are ready.")
        return 0

    host = "0.0.0.0" if args.lan else args.host
    api_command = [
        str(VENV_PYTHON),
        str(PROJECT_ROOT / "scripts" / "start_api.py"),
        "--host",
        host,
        "--port",
        str(args.api_port),
    ]
    frontend_command = [
        npm,
        "run",
        "dev",
        "--",
        "--host",
        host,
        "--port",
        str(args.frontend_port),
        "--strictPort",
    ]
    environment = os.environ.copy()
    environment.setdefault(
        "VITE_API_PROXY_TARGET", f"http://127.0.0.1:{args.api_port}"
    )

    print(f"Frontend: http://127.0.0.1:{args.frontend_port}")
    print(f"API:      http://127.0.0.1:{args.api_port}")
    print("Press Ctrl+C to stop both servers.\n")

    processes: list[subprocess.Popen[bytes]] = []
    try:
        processes.append(
            subprocess.Popen(api_command, cwd=PROJECT_ROOT, env=environment, **process_options())
        )
        processes.append(
            subprocess.Popen(
                frontend_command,
                cwd=FRONTEND_ROOT,
                env=environment,
                **process_options(),
            )
        )
        while True:
            for process in processes:
                return_code = process.poll()
                if return_code is not None:
                    print(f"\nA development server stopped with exit code {return_code}.")
                    return return_code
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nStopping Oh My Exam...")
        return 0
    finally:
        for process in reversed(processes):
            stop_process_tree(process)


if __name__ == "__main__":
    raise SystemExit(main())
