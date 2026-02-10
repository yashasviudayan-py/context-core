# Contributing to Context Core

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone
git clone https://github.com/yashasviudayan-py/context-core.git
cd context-core

# Create venv
python3 -m venv .venv
source .venv/bin/activate

# Install with dev dependencies
pip install -e ".[dev]"

# Verify
pytest
```

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=context_core

# Specific test file
pytest tests/test_rag.py -v
```

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

Configuration is in `pyproject.toml`:
- Python 3.12 target
- 100 character line length

## Project Conventions

- **Dataclasses** for all data models (frozen where appropriate)
- **Click** for CLI commands with Rich output
- **Lazy imports** for optional modules (watcher, oracle) to keep CLI fast
- **Mock external services** in tests — no Ollama required to run the test suite
- **SHA-256 content hashing** for document deduplication
- **`raise SystemExit(1)`** for CLI errors, not `sys.exit()`

## Submitting Changes

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run `pytest` and `ruff check` to verify
5. Commit with a clear message
6. Push and open a pull request

## Reporting Issues

Open an issue on GitHub with:
- Steps to reproduce
- Expected vs actual behavior
- Python version, OS, Ollama version
