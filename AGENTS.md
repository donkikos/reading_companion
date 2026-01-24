# Repository Guidelines

## Project Structure & Module Organization
- `main.py` hosts the FastAPI app and HTTP API for uploads, sync, and ingestion verification.
- `ingest.py` contains the EPUB ingestion pipeline and Qdrant/embedding integration helpers.
- `db.py` manages the SQLite state in `.data/state.db` (books, chapters, reading state).
- `server.py` runs the MCP tool server for querying book context.
- `static/` holds the client UI (`index.html`, `script.js`, `style.css`).
- `tests/` contains pytest suites; `tests/fixtures/` holds test fixtures.
- `scripts/compose_healthcheck.py` is used by Docker Compose health checks.
- `scripts/purge_qdrant.py` drops the Qdrant collection for a full embedding reset.
- `docs/` and `plan/` contain project notes and PRD artifacts.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` installs Python dependencies.
- `python main.py` runs the API (or `uvicorn main:app --reload` for live reload).
- `python server.py` runs the MCP tool server.
- `docker compose up --build` starts the app + Qdrant + TEI stack.
- Some scripts under `scripts/` import top-level modules; run them with `PYTHONPATH=/app` when needed.
- `ruff format` formats Python files (line length 100).
- `ruff check .` runs linting.
- `pytest` runs the test suite.

## Browser Automation

Use `agent-browser` for web automation. Run `agent-browser --help` for all commands.

Core workflow:
1. `agent-browser open <url>` - Navigate to page
2. `agent-browser snapshot -i` - Get interactive elements with refs (@e1, @e2)
3. `agent-browser click @e1` / `fill @e2 "text"` - Interact using refs
4. Re-snapshot after page changes

## Coding Style & Naming Conventions
- Python uses 4-space indentation.
- Apply `ruff format` before linting; keep lines at 100 chars.
- Use `snake_case` for functions/variables, `PascalCase` for classes, and `UPPER_CASE` for constants.
- Persist local state under `.data/` (books, Qdrant local store if `QDRANT_PATH`, SQLite); avoid committing generated data.

## Testing Guidelines
- Tests are in `tests/test_*.py` and use `pytest`.
- `tests/conftest.py` adds the repo root to `sys.path` so single-test runs can import top-level modules.
- Integration tests for Qdrant/TEI skip if services are unavailable; run `docker compose up` for full coverage.
- Add tests alongside new ingestion or API behavior; prefer focused unit tests over large fixtures.

## Commit & Pull Request Guidelines
- Git history uses Conventional Commits (`fix: ...`); follow `feat:`, `fix:`, `chore:`, etc.
- PRs should include a short summary, tests run, and any config/data changes.
- For UI changes in `static/`, include screenshots or a brief screen recording.

## Configuration & Services
- Runtime config relies on `QDRANT_HOST`, `QDRANT_PORT`, and `TEI_BASE_URL` (see `docker-compose.yml`).
- Local data lives in `.data/`; if debugging, you can remove this directory to reset state.
