"""Seeded synthetic tabular data from a declarative schema.

Ten column types, uniqueness, nullability, foreign keys across tables and CSV or JSONL export.
"""

from __future__ import annotations

import logging

from .errors import GenerationError, SchemaError, SyntheticDataError
from .export import to_csv, to_jsonl, write_all
from .generator import generate
from .schema import Column, Schema, Table, validate_schema

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "Column",
    "GenerationError",
    "Schema",
    "SchemaError",
    "SyntheticDataError",
    "Table",
    "__version__",
    "generate",
    "to_csv",
    "to_jsonl",
    "validate_schema",
    "write_all",
]

__version__ = "0.1.0"
