# Contributing Guide

Thank you for your interest in py-image-compress-mcp! We welcome all forms of contributions.

## Development Setup

### Requirements
- Python 3.10+
- uv package manager

### Quick Setup

```bash
# 1. Fork and clone
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp

# 2. Install dependencies
uv sync --extra dev

# 3. Install pre-commit hooks
uv run pre-commit install

# 4. Run tests
make test
```

## Development Commands

```bash
# Format and check code
make format
make lint

# Run tests
make test

# Full CI check
make ci
```

## Code Standards
- Python 3.10+ with type annotations
- Formatted with ruff
- All tests must pass

## Pull Request Process
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run `make ci` to ensure all checks pass
5. Submit a pull request

Thank you for contributing!
