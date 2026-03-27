# Repository Guidelines

## Project Structure & Module Organization

Core application code lives in [`zen_prompt/`](/Users/anhld/Works/code/zen/quotes/zen_prompt), including the CLI entrypoint in `cli.py`, command modules in `commands/`, the Goodreads spider in `spider.py`, persistence in `db.py`, and bundled photo assets in `photos/`. Tests live in [`tests/`](/Users/anhld/Works/code/zen/quotes/tests). User-facing docs are in [`README.md`](/Users/anhld/Works/code/zen/quotes/README.md) and [`docs/`](/Users/anhld/Works/code/zen/quotes/docs). Helper scripts such as [`scripts/zen-prompt`](/Users/anhld/Works/code/zen/quotes/scripts/zen-prompt), `collect`, and `release` live in [`scripts/`](/Users/anhld/Works/code/zen/quotes/scripts).

## Build, Test, and Development Commands

- `uv sync`: install project dependencies into the local environment.
- `UV_CACHE_DIR=/tmp/uv-cache uv run zen-prompt --help`: run the CLI locally.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest`: run the full test suite.
- `UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_cli.py`: run one focused test module.
- `uv build`: build wheel and source distributions.

Use the wrapper script for local manual testing:

```bash
scripts/zen-prompt random
scripts/zen-prompt crawl --tags inspirational,life
```

## Coding Style & Naming Conventions

Use Python 3.13, 4-space indentation, and type hints where practical. Prefer small command functions with explicit `typer.Option(...)` / `typer.Argument(...)` declarations. Module and package names use `snake_case`; CLI command names and distribution names use `kebab-case` such as `zen-prompt`. Keep help text concise and user-facing. Follow existing patterns instead of introducing new abstractions casually.

## Testing Guidelines

Tests use `pytest`. Add or update tests in `tests/test_*.py` alongside code changes. Prefer narrow unit tests for command behavior, DB helpers, and spider parsing. When changing CLI contracts, update help-surface assertions in `tests/test_cli.py`. Run the full suite before finalizing changes.

## Commit & Pull Request Guidelines

Use Conventional Commits, e.g. `feat(random): default to monochrome photo` or `test(cli): align help text`. Keep commits logically scoped. PRs should explain what changed, why it changed, and note any CLI contract or packaging impact. Include command output or screenshots when changing terminal UX or docs examples.

## Security & Configuration Tips

Do not commit generated artifacts from `dist/`, local caches, or SQLite databases unless the change explicitly updates shipped data. Prefer `UV_CACHE_DIR=/tmp/uv-cache` in sandboxed environments to avoid cache permission issues.
