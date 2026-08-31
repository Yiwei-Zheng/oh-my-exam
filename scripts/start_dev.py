#!/usr/bin/env python3
"""Start the API and Next.js development server as one local process group."""

from __future__ import annotations

import argparse
import ipaddress
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlsplit


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
VENV_PYTHON = PROJECT_ROOT / ".venv" / (
    "Scripts/python.exe" if os.name == "nt" else "bin/python"
)
VENV_QR = PROJECT_ROOT / ".venv" / (
    "Scripts/qr.exe" if os.name == "nt" else "bin/qr"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the Oh My Exam API and frontend development server."
    )
    host_group = parser.add_mutually_exclusive_group()
    host_group.add_argument("--host", default="0.0.0.0")
    host_group.add_argument(
        "--local",
        action="store_const",
        dest="host",
        const="127.0.0.1",
        help="Listen on localhost only and do not show a LAN QR code.",
    )
    host_group.add_argument(
        "--lan",
        action="store_const",
        dest="host",
        const="0.0.0.0",
        help="Listen on all interfaces (the default; retained for compatibility).",
    )
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=4173)
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
        raise RuntimeError("npm was not found on PATH. Install Node.js 20.19 or later.")
    if not (FRONTEND_ROOT / "node_modules").is_dir():
        raise RuntimeError("Frontend dependencies not found. Run: cd frontend && npm install")
    if not VENV_QR.is_file():
        raise RuntimeError(
            "QR code support not found. Run: python scripts/setup_env.py --group all"
        )
    return npm


def discover_lan_ip() -> str | None:
    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("192.0.2.1", 80))
            candidates.append(probe.getsockname()[0])
    except OSError:
        pass

    try:
        candidates.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass

    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if isinstance(address, ipaddress.IPv4Address) and not (
            address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
        ):
            return candidate
    return None


def frontend_access_url(host: str, port: int) -> str | None:
    if host == "0.0.0.0":
        host = discover_lan_ip() or ""
    if not host:
        return None
    try:
        address = ipaddress.ip_address(host)
        if address.is_loopback:
            return None
        if isinstance(address, ipaddress.IPv6Address):
            host = f"[{host}]"
    except ValueError:
        if host.lower() == "localhost":
            return None
    return f"http://{host}:{port}"


def allowed_dev_origins(existing: str, lan_url: str | None) -> str:
    configured_origins = [
        origin.strip() for origin in existing.split(",") if origin.strip()
    ]
    lan_host = urlsplit(lan_url).hostname if lan_url else None
    if lan_host and lan_host not in configured_origins:
        configured_origins.append(lan_host)
    return ",".join(configured_origins)


def print_access_qr(url: str) -> None:
    print("\nScan to open on this local network / 扫码从局域网访问:", flush=True)
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    subprocess.run(
        [str(VENV_QR), "--ascii", url],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )
    print(f"LAN:      {url}")


def require_available_port(port: int, label: str) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            raise RuntimeError(f"{label} port {port} is already in use.")


def wait_for_port(
    port: int,
    processes: list[subprocess.Popen[bytes]],
    timeout_seconds: float = 30,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if any(process.poll() is not None for process in processes):
            return False
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


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

    host = args.host
    api_command = [
        str(VENV_PYTHON),
        str(PROJECT_ROOT / "scripts" / "start_api.py"),
        "--host",
        "127.0.0.1",
        "--port",
        str(args.api_port),
    ]
    frontend_command = [
        npm,
        "run",
        "dev",
        "--",
        "--hostname",
        host,
        "--port",
        str(args.frontend_port),
    ]
    environment = os.environ.copy()
    environment.setdefault(
        "OME_API_PROXY_TARGET", f"http://127.0.0.1:{args.api_port}"
    )

    lan_url = frontend_access_url(host, args.frontend_port)
    environment["OME_ALLOWED_DEV_ORIGINS"] = allowed_dev_origins(
        environment.get("OME_ALLOWED_DEV_ORIGINS", ""), lan_url
    )
    print(f"Local:    http://127.0.0.1:{args.frontend_port}")
    print(f"API:      http://127.0.0.1:{args.api_port} (local only)")
    if lan_url is None and host != "127.0.0.1":
        print("LAN:      unavailable (no active LAN IPv4 address was found)")
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
        if lan_url is not None:
            if wait_for_port(args.frontend_port, processes):
                print_access_qr(lan_url)
            elif all(process.poll() is None for process in processes):
                print("LAN QR code was skipped because the frontend did not become ready.")
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
