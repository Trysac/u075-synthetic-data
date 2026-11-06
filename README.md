# synthetic-data

[![PyPI version](https://img.shields.io/pypi/v/trysac-synthetic-data)](https://pypi.org/project/trysac-synthetic-data/)
[![License: MIT](https://img.shields.io/pypi/l/trysac-synthetic-data)](LICENSE)
[![CI](https://github.com/Trysac/u075-synthetic-data/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u075-synthetic-data/actions/workflows/ci.yml)

Seeded synthetic tabular data from a declarative schema: ten column types, uniqueness, nullability, foreign keys across tables and CSV or JSONL export

## Problem

Describe in two or three sentences the concrete problem this utility solves, who hits it, and what
they do today without it. Replace this paragraph when the first real feature lands.

## Install

```sh
pip install trysac-synthetic-data
# or
uv add trysac-synthetic-data
```

Requires Python 3.10 or newer. No runtime dependencies.

## Usage

```python
import synthetic_data

# normalize() trims surrounding whitespace and lower-cases the text.
print(synthetic_data.normalize("  Hello World "))  # -> "hello world"

# Blank input is rejected explicitly instead of returning an empty string.
try:
    synthetic_data.normalize("   ")
except ValueError as exc:
    print(f"rejected: {exc}")
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md) and [decisions](docs/decisions/)
- [Testing](docs/TESTING.md) and [security](docs/SECURITY.md)
- [Project record](docs/PROJECT.md) and [stack](docs/STACK.md)
- [Changelog](CHANGELOG.md) and [contributing guide](CONTRIBUTING.md)

## License

[MIT](LICENSE) (c) 2026 Miguel Gomez
