# Python dependencies

The repository uses one Python virtual environment at `.venv/`. Dependency
entry points remain separated by responsibility:

- `backend.txt`: production hosted API dependencies.
- `backend-dev.txt`: editable backend plus test dependencies.
- `data-processing.txt`: downloaders, splitters, packers, GUIs, OCR, and tests.

`backend.txt` is the production installation entry point and does not install
test tooling. From the repository root, create or update the shared environment
on Windows, Linux, or macOS with:

```console
python scripts/setup_env.py --group all
```

Linux distributions that do not provide a `python` command should use `python3`.
Select `backend`, `backend-dev`, or `data-processing` when only one dependency
group needs to be refreshed. `all` installs `backend-dev` and data processing for
a complete development environment.

The PowerShell `setup.ps1` command remains a Windows compatibility wrapper around
the Python script. The Python script fixes the project index to official PyPI,
keeps pip cache and temporary builds under `.venv/`, and writes a venv-local pip
configuration; it does not install packages globally.

Virtual environments are operating-system specific. Do not copy `.venv/` from
Windows to Linux; run the setup script again on the deployment host.

The individual packages continue to own their dependency declarations in their
respective `pyproject.toml` files. These requirement files are installation
entry points, not duplicate version lists.
