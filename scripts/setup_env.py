"""Create the repository-local Python environment and install one dependency group."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_ROOT = PROJECT_ROOT / ".venv"
INSTALL_TARGETS = {
    "backend": "./backend",
    "backend-dev": "./backend[test]",
    "data-processing": "./backend[ocr]",
    "all": "./backend[test,ocr]",
}


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_ROOT / "Scripts" / "python.exe"
    return VENV_ROOT / "bin" / "python"


def ensure_venv() -> Path:
    python_path = venv_python()
    if python_path.is_file():
        return python_path

    if VENV_ROOT.exists() and any(VENV_ROOT.iterdir()):
        raise RuntimeError(
            f"{VENV_ROOT} is not a usable virtual environment for this operating "
            "system. Remove it and run this command again."
        )

    venv.EnvBuilder(with_pip=True).create(VENV_ROOT)
    if not python_path.is_file():
        raise RuntimeError(f"Virtual environment creation did not produce {python_path}.")
    return python_path


def local_install_environment() -> dict[str, str]:
    pip_cache = VENV_ROOT / ".pip-cache"
    build_temp = VENV_ROOT / ".tmp"
    pip_cache.mkdir(parents=True, exist_ok=True)
    build_temp.mkdir(parents=True, exist_ok=True)

    pip_config = VENV_ROOT / ("pip.ini" if os.name == "nt" else "pip.conf")
    pip_config.write_text(
        "[global]\n"
        "index-url = https://pypi.org/simple\n"
        f"cache-dir = {pip_cache.as_posix()}\n"
        "disable-pip-version-check = true\n",
        encoding="utf-8",
    )

    environment = os.environ.copy()
    environment.update(
        {
            "PIP_CONFIG_FILE": str(pip_config),
            "PIP_CACHE_DIR": str(pip_cache),
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_INDEX_URL": "https://pypi.org/simple",
            "TEMP": str(build_temp),
            "TMP": str(build_temp),
            "TMPDIR": str(build_temp),
        }
    )
    return environment


def install_group(group: str) -> None:
    python_path = ensure_venv()
    environment = local_install_environment()

    subprocess.run(
        [str(python_path), "-m", "pip", "install", "--editable", INSTALL_TARGETS[group]],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create .venv and install a project dependency group."
    )
    parser.add_argument(
        "--group",
        choices=tuple(INSTALL_TARGETS),
        default="all",
        help="Dependency group to install (default: all).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        install_group(args.group)
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Environment setup failed: {error}", file=sys.stderr)
        return 1

    print(f"Installed dependency group '{args.group}' into {VENV_ROOT}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
