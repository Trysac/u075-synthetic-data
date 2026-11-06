"""Typed errors for synthetic_data."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

ErrorCode = Literal["invalid_schema", "too_large", "generation_failed"]


class SyntheticDataError(Exception):
    """Base error of the library with a stable machine-readable ``code``."""

    def __init__(self, message: str, code: ErrorCode) -> None:
        super().__init__(message[:200])
        self.code: ErrorCode = code


class SchemaError(SyntheticDataError):
    """The schema (or an argument) is invalid or too large; see ``problems``."""

    def __init__(self, problems: Iterable[str], code: ErrorCode = "invalid_schema") -> None:
        self.problems: list[str] = list(problems)
        super().__init__("; ".join(self.problems) or "invalid schema", code)


class GenerationError(SyntheticDataError):
    """Generation could not satisfy a constraint (for example uniqueness)."""

    def __init__(self, message: str) -> None:
        super().__init__(message, "generation_failed")
