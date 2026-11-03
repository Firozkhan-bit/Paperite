# Paperite

Paperite is an offline-first desktop inventory application for a small
stationery shop. It is designed to run entirely on a single Windows machine,
with no network dependency.

## Stack

- **Python** 3.12
- **PySide6** (Qt for Python) for the user interface
- **SQLite** via the standard-library `sqlite3` module for local storage
- **pytest** for the test harness

> Export features (Excel/PDF) are planned for a later phase. Their
> dependencies (`openpyxl`, `ReportLab`) are intentionally **not** installed
> in this phase.

## Project layout

```
Paperite/
  src/
    main.py          Application entry point
    ui/              User interface layer
    services/        Application services layer
    database/        Data access layer
    models/          Domain models
    utils/           Shared utilities
  tests/             pytest test suite
  docs/              Project documentation
  requirements.txt   Pinned Python dependencies
```

## Getting started

### 1. Create a virtual environment

```
python -m venv .venv
```

Activate it:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Windows (cmd):       `.venv\Scripts\activate.bat`
- Linux / macOS:        `source .venv/bin/activate`

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Run the application

```
python src/main.py
```

This opens a single empty window titled "Paperite".

### 4. Run the tests

```
pytest
```

## Status

**Phase 1 -- Foundation.** The application currently opens a proof-of-concept
window and the test harness is in place. Business features, the database, and
styling are not yet implemented.
