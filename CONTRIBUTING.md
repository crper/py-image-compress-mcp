# Contributing Guide

Thank you for your interest in py-image-compress-mcp! We welcome all forms of contributions.

## Development Setup

### Requirements
- Python 3.10+
- uv package manager

### Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp

# 2. Install dependencies
uv sync --extra dev

# 3. Install pre-commit hooks
uv run pre-commit install

# 4. Run the test suite
make test
```

## Development Commands

```bash
# Format, lint, type-check, and test in one pass
make dev

# Run tests
make test

# Run type checking
make typecheck

# Run benchmarks
make benchmark

# Run the MCP example script
make examples
```

The CI workflow currently validates the repository with:

```bash
uv run ruff check src tests examples scripts
uv run ruff format --check src tests examples scripts
uv run mypy src tests
uv run pytest tests/ --cov=src/py_image_compress_mcp --cov-report=xml
```

## Code Standards
- Python 3.10+ with type annotations
- Formatted with ruff
- All tests must pass
- Keep the public MCP surface small and explicit

## Pull Request Process
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run the validation commands above, or at minimum `make dev`
5. Submit a pull request

Thank you for contributing!
