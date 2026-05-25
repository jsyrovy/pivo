# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Project Overview

Python 3.14 application that scrapes Untappd beer data, tracks consumption stats
among friends ("Pivni valka"), monitors pub tap lists, and archives check-ins via
RSS. Outputs a static HTML dashboard published to GitHub Pages.

Package manager: **uv** (Astral). No virtual environment activation needed -- use
`uv run` for all commands.

## Build & Run Commands

| Command                  | Description                                   |
|--------------------------|-----------------------------------------------|
| `make test`              | Run full test suite (`uv run --dev -m pytest`) |
| `make lint`              | Lint with ruff (`uvx ruff check`)             |
| `make lint-fix`          | Auto-fix lint issues (`uvx ruff check --fix`) |
| `make format`            | Format Python code (`uvx ruff format`)         |
| `make format-html`       | Format HTML templates (`uvx djlint --reformat`)|
| `make lint-html`         | Lint HTML templates (`uvx djlint --lint`)      |
| `make mypy`              | Type-check (strict on src, relaxed on tests)  |
| `make ty`                | Experimental type-check (`uvx ty check`)      |
| `make coverage`          | Run tests with coverage report                |
| `make before-commit`     | format + format-html + test + lint-fix + lint-html + mypy (run before committing) |
| `make publish-pivni-valka` | Regenerate static HTML output (no test data)          |

### Running a Single Test

```sh
# Single test file
uv run --dev -m pytest tests/pivni_valka/test_pivni_valka.py

# Single test function
uv run --dev -m pytest tests/pivni_valka/test_pivni_valka.py::test_parse_unique_beers_count

# Single test directory / module
uv run --dev -m pytest tests/untappd_pairing/

# With verbose output
uv run --dev -m pytest -v tests/pivni_valka/test_pivni_valka.py::test_parse_unique_beers_count
```

### Running the Application

```sh
make run-pivni-valka                 # Full run (scrapes + notifies)
make run-pivni-valka-notificationless # No push notifications
make run-pivni-valka-local           # Skip downloading, use cached data
make run-untappd-pairing             # Pair tap beers with Untappd entries
make run-archivist                   # Run RSS archiver
```

## CI Pipeline

On every push (`.github/workflows/tests.yml`), CI runs in parallel:
- `make test` (pytest)
- `make mypy` (type checking)
- `make lint` (ruff)
- Smoke test for the pivni-valka pipeline

All checks must pass before merging.

## Code Style

### Formatting & Linting

- **Ruff** with `lint.select = ["ALL"]` -- nearly every rule is enabled
- **djLint** for HTML/Jinja2 templates (`profile = "jinja"`, config in `pyproject.toml`)
- **ruff**, **djLint** and **ty** are run via `uvx` (not installed as dev dependencies)
- **Line length:** 120 characters
- **Target version:** py314
- Run `before-commit` before committing -- **do not commit if it fails**
- Use `# noqa: XXXX` sparingly and only with a specific rule code

### Imports

- Standard library first, third-party second, local third (enforced by ruff `I` rules)
- Use **absolute imports**: `from database.models import PivniValka`, not relative imports
- Unused imports are only allowed in `__init__.py` files (re-exports)

### Type Annotations

- **Full type annotations on all function signatures** in source code (mypy `--strict`)
- Tests do **not** require type annotations
- Use modern Python syntax: `dict[str, int]`, `list[str]`, `str | None`, `tuple[str, ...]`
- Use `Literal` for constrained string types
- Use SQLAlchemy `Mapped[...]` for ORM column types

### Naming Conventions

- `snake_case` for functions, variables, modules, file names
- `PascalCase` for classes: `PivniValka`, `BaseRobot`, `OrmRobot`
- `UPPER_SNAKE_CASE` for module-level constants: `ENCODING`, `BASE_URL`, `TIMEOUT`
- Prefix private methods/attributes with `_`: `_main()`, `_args`

### Error Handling

- Raise specific exceptions with clear messages: `raise ValueError("Cannot parse user profile.")`
- Define custom exception classes when appropriate: `class UserNotFoundError(Exception)`
- Use exception chaining: `raise ... from e`
- Use `r.raise_for_status()` after HTTP requests
- Check required env vars early and raise `OSError` with a descriptive message

### Logging

- Use the `logging` module for all diagnostic output -- never `print` (enforced by ruff `T201`)
- Each module gets its own logger: `logger = logging.getLogger(__name__)`
- Logging is configured centrally via `configure_logging()` from `utils/logging.py`
- Entry point scripts (`run_*.py`) call `configure_logging()` **before** importing robot
  classes (because `database/orm.py` executes at import time)
- Log level mapping:
  - `logger.info` -- status messages (record saved, dump loaded, etc.)
  - `logger.debug` -- routine/verbose output (skipped records, cache hits)
  - `logger.exception` -- errors inside `except` blocks (includes traceback automatically)
  - `logger.error` -- error conditions outside `except` blocks
- Use `%s`-style placeholders in log calls, not f-strings: `logger.info("Saved: %s", record)`

### Data Classes & Patterns

- Use `@dataclass` extensively for structured data (`frozen=True`, `kw_only=True` where appropriate)
- Use `pathlib.Path` consistently -- never `os.path`
- Use `httpx` with HTTP/2 for HTTP requests -- not `requests`
- Use context managers for DB sessions and file I/O
- Template Method pattern: `BaseRobot.run()` calls `_main()` (override in subclasses)

### Test Conventions

- Framework: **pytest** (plain functions, no test classes)
- Test files mirror source structure: `tests/pivni_valka/test_pivni_valka.py`
- Every test gets a fresh in-memory SQLite DB (autouse fixture in `conftest.py`)
- Use `unittest.mock` for mocking (`mock.patch`, `MagicMock`)
- Use `pytest.raises` for exception assertions, check message via `excinfo.value`
- Magic values and `assert` are permitted in tests (ruff rules relaxed)
- Private member access is permitted in tests
- Mock all IO and network operations -- no integration tests
- Use `caplog` fixture for asserting log output (not `capsys`)

### What NOT to Do

- Do not add docstrings -- all `D1xx` rules are intentionally disabled
- Do not use `os.path` -- use `pathlib.Path`
- Do not use `requests` -- use `httpx`
- Do not use `print` -- use `logging` (enforced by ruff `T201`)
- Do not use relative imports
- Do not add type annotations to test functions

## Performance Patterns

- **No N+1 query loops** -- never run a `SELECT` inside a loop for each row/date/user.
  Fetch data with a single query and process in Python (e.g. `itertools.accumulate`
  for cumulative sums).
- **Compute once, slice many** -- chart data is computed once for the full date range
  (`get_all_chart_data()`) and then sliced for 14/30/365/all-day views
  (`slice_chart_data()`). Follow this pattern for any new chart types.

## Frontend / Templates

- **Tailwind CSS** via CDN (no build step) and **ApexCharts** for charts
- Dark/light theme toggle with `localStorage` persistence; dark is the default
- **Data handoff:** Python lists are passed to JavaScript through Jinja2's
  built-in `{{ data | tojson }}` filter, which calls `json.dumps()` and produces
  valid, properly escaped JavaScript literals.
- **Single-page chart switching:** all chart time periods (14/30/365/all days) are
  embedded as inline data in the main `index.html`. Users switch between periods
  via tabs; JavaScript calls `chart.updateOptions()` to swap data instantly without
  page navigation. The active period is stored in the URL hash (`#14`, `#30`,
  `#365`, `#all`) so links to specific periods can be shared.
- **One generated page:** the dashboard is a single `index.html` at the repo root
  (for GitHub Pages). There are no separate chart detail pages.

## Project Structure

```
untappd/
  archivist/         # RSS feed check-in archiver
  data/              # SQLite dumps (data_dump.sql, test_dump.sql)
  database/          # SQLAlchemy ORM models and DB utilities
  maintenance/       # One-off maintenance scripts
  pivni_valka/       # Main stats tracking module
    stats/           # Chart data and tile computations
  robot/             # Base runner abstractions (BaseRobot, OrmRobot)
  templates/         # Jinja2 HTML templates
  tests/             # pytest test suite (mirrors source layout)
  utils/             # Shared utilities (HTTP, templates, users, logging)
  web/               # Generated static output (GitHub Pages) -- DO NOT EDIT
  index.html         # Generated main dashboard -- DO NOT EDIT (at repo root for GitHub Pages)
  run_*.py           # Entry point scripts
  Makefile           # All dev commands
  pyproject.toml     # Project config (uv-managed)
  ruff.toml          # Linter/formatter config
```

## Database

- In-memory SQLite via SQLAlchemy ORM
- Persistence via SQL dump files in `data/`
- Production data: `data/data_dump.sql`
- Test fixture data: `data/test_dump.sql`
- SQL dumps contain both `CREATE TABLE` and `INSERT` statements (full schema + data)
- Test detection: `"pytest" in sys.modules` switches to test DB automatically
