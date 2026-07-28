# parsekit

![CI](https://github.com/acme/parsekit/actions/workflows/test.yml/badge.svg)

Small parsing helper with no runtime dependencies.

## Installation

```bash
pip install -e .
```

Requires Python `>=3.11` (from `pyproject.toml`).

## Usage

```python
from parsekit import parse

parse("hello")
```

## API

| Symbol | Description |
|--------|-------------|
| `parse(text)` | Parse a string and return a dict |

The public surface is re-exported from `src/parsekit/__init__.py`.

## Testing

```bash
pytest
```

Tests live under `tests` and run in CI via `.github/workflows/test.yml`.

## License

Not found in repo — consider adding a LICENSE file.

## Documentation Maintenance

Update this README when:

- the public API in `src/parsekit/__init__.py` changes
- `requires-python` changes in `pyproject.toml`
- the CI workflow changes
