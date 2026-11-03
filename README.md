# Paperite

Paperite is an offline-first desktop inventory application for a small
stationery shop. It runs entirely on a single Windows machine, with no network
dependency.

## Stack

- **Python** 3.12
- **PySide6** (Qt for Python) for the user interface
- **SQLite** via the standard-library `sqlite3` module for local storage
- **pytest** for the test harness

> Export features (Excel/PDF) are planned for a later phase. Their dependencies
> (`openpyxl`, `ReportLab`) are intentionally **not** installed yet.

## Project layout

```
Paperite/
  src/
    main.py                    Application entry point (DB init + window)
    ui/
      theme.py                 Design system: tokens, QSS, reusable widgets
      main_window.py           App shell: sidebar nav + stacked content pages
      products/
        products_page.py       Products listing (search, filter, sort, archive)
        product_dialog.py      Add/Edit product dialog with inline validation
    services/
      product_service.py       Product business logic (typed errors, no Qt)
    database/
      connection.py            SQLite connection (FKs ON, row factory, path)
      schema.py                init_db() -- migration runner entry point
      migrations.py            Versioned, idempotent migration runner (v1)
    models/                    Domain models (reserved)
    utils/
      money.py                 Paise <-> "₹X.XX" formatting (no floats)
  tests/                       pytest test suite
  docs/                        Project documentation
  requirements.txt             Pinned Python dependencies
  pytest.ini                   Test runner configuration
```

## Getting started

### 1. Create a virtual environment

```
python -m venv .venv
```

Activate it:

- Windows (PowerShell): `.venv\Scripts\Activate.ps1`
- Windows (cmd):       `.venv\Scripts\activate.bat`
- Linux / macOS:       `source .venv/bin/activate`

### 2. Install dependencies

```
pip install -r requirements.txt
```

### 3. Run the application

```
python src/main.py
```

On first launch the app initialises a local SQLite database in your per-user
application-data folder and migrates it to the latest schema. On Windows the
database lives at `%APPDATA%\Paperite\paperite.db`. You can point the app at a
different database (useful for testing) by setting the `PAPERITE_DB_PATH`
environment variable before launching.

### 4. Run the tests

```
pytest
```

The pure-Python tests (database, money, product service, smoke) run on any
host. The MainWindow navigation tests need the Qt GUI libraries and are skipped
on headless hosts (e.g. a CI container missing `libEGL.so.1`); on a normal
Windows desktop they run for real.

## What works right now (Phases 1-4)

- **Application shell** — a resizable window with a left sidebar (Dashboard,
  Products, Categories, Suppliers, Purchases, Sales, Reports, Settings) and a
  right content area that swaps pages. All sections except Products are clearly
  labelled placeholders.
- **Design system** — a single source of truth for colours, typography,
  spacing, and reusable widgets (primary/secondary buttons, input fields,
  combo boxes, spin boxes, tables, page headers, sidebar nav items). Calm
  style: subtle borders, no gradients, no neon, consistent corner radius.
- **Database foundation** — a versioned, idempotent migration runner with a
  `schema_version` table. v1 creates the initial schema (categories, products,
  suppliers, purchases, purchase_items, sales, sale_items, stock_movements).
  Foreign keys are enforced; money is stored as integer paise; quantities are
  whole numbers; CHECK and UNIQUE constraints guard data integrity.
- **Products end-to-end** — a Products page with a searchable, sortable,
  filterable table; an Add/Edit dialog with inline validation; soft-archive
  (products are never hard-deleted). Validation surfaces typed errors inline
  rather than as raw database tracebacks.

## Not yet built (future phases)

- Stock movements on product create/edit (an initial quantity is stored on the
  product row, but no `stock_movements` ledger entry is written yet).
- Categories, Suppliers, Purchases, Sales, Reports, Settings screens.
- Excel/PDF export (openpyxl / ReportLab).

## Data model notes

Money is stored as **integer paise** (1 rupee = 100 paise) and is never held as
a float. Display conversions go through `src/utils/money.py`. Quantities are
whole numbers. See `src/database/migrations.py` for the full v1 schema and the
migration strategy for adding future versions.
