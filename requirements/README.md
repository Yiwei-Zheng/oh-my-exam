# Python dependencies

The repository uses one Python virtual environment at `.venv/`. Dependency
entry points remain separated by responsibility:

- `backend.txt`: hosted API and backend tests.
- `data-processing.txt`: downloaders, splitters, packers, GUIs, OCR, and tests.

From the repository root, create or update the shared environment with:

```powershell
requirements\setup.ps1 -Group all
```

Use `-Group backend` or `-Group data-processing` when only one dependency group
needs to be refreshed. The setup script fixes the project index to official PyPI,
keeps pip cache and temporary builds under `.venv/`, and writes the venv-local
`.venv/pip.ini`; it does not install packages globally.

The individual packages continue to own their dependency declarations in their
respective `pyproject.toml` files. These requirement files are installation
entry points, not duplicate version lists.
