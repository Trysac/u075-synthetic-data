"""CSV and JSON Lines export."""

from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TextIO

from .errors import SchemaError
from .schema import NAME_RE, Schema


def to_csv(
    rows: Sequence[Mapping[str, Any]], out: TextIO, columns: Sequence[str] | None = None
) -> int:
    """Write ``rows`` as CSV (``\\n`` line endings, None as empty); return the row count.

    The header is ``columns`` or the keys of the first row; nothing is written for no header.
    """
    header = list(columns) if columns is not None else (list(rows[0]) if rows else [])
    if not header:
        return len(rows)
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(["" if row.get(c) is None else row.get(c) for c in header])
    return len(rows)


def to_jsonl(rows: Sequence[Mapping[str, Any]], out: TextIO) -> int:
    """Write ``rows`` as JSON Lines in key order; return the row count."""
    for row in rows:
        out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def write_all(
    data: Mapping[str, Sequence[Mapping[str, Any]]],
    directory: Path,
    fmt: Literal["csv", "jsonl"],
    schema: Schema | None = None,
) -> list[Path]:
    """Write ``<table>.<fmt>`` for each table into ``directory`` and return the paths."""
    if fmt not in ("csv", "jsonl"):
        raise SchemaError(["fmt must be 'csv' or 'jsonl'"])
    for name in data:
        if not isinstance(name, str) or not NAME_RE.match(name):
            raise SchemaError(["invalid table name for a file"])
    cols = {t.name: [c.name for c in t.columns] for t in schema.tables} if schema else {}
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for name, rows in data.items():
        path = directory / f"{name}.{fmt}"
        with path.open("w", encoding="utf-8", newline="") as fh:
            if fmt == "csv":
                to_csv(rows, fh, cols.get(name))
            else:
                to_jsonl(rows, fh)
        paths.append(path)
    return paths
