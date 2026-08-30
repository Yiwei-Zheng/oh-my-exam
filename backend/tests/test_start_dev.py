from __future__ import annotations

import importlib.util
from pathlib import Path
import socket


START_DEV_PATH = Path(__file__).resolve().parents[2] / "scripts" / "start_dev.py"
SPEC = importlib.util.spec_from_file_location("start_dev", START_DEV_PATH)
assert SPEC is not None and SPEC.loader is not None
start_dev = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(start_dev)


class RunningProcess:
    def poll(self) -> None:
        return None


def test_frontend_access_url_uses_discovered_lan_ip(monkeypatch) -> None:
    monkeypatch.setattr(start_dev, "discover_lan_ip", lambda: "192.168.10.4")

    assert start_dev.frontend_access_url("0.0.0.0", 4173) == (
        "http://192.168.10.4:4173"
    )
    assert start_dev.frontend_access_url("127.0.0.1", 4173) is None


def test_frontend_access_url_brackets_ipv6_address() -> None:
    assert start_dev.frontend_access_url("fd00::1", 4173) == "http://[fd00::1]:4173"


def test_wait_for_port_reports_ready_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()

        assert start_dev.wait_for_port(
            listener.getsockname()[1], [RunningProcess()], timeout_seconds=0.5
        )
