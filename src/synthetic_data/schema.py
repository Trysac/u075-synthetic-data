"""Schema validation for synthetic_data."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, TypeGuard

from .errors import SchemaError
from .words import FIRST_NAMES, LAST_NAMES

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}\Z")
PLACEHOLDER = re.compile(r"\{seq(?::0([1-9]|1[0-9]|20)d)?\}")

MAX_TABLES = 100
MAX_COLUMNS = 200
MAX_TOTAL_ROWS = 1_000_000
MAX_TEMPLATE = 200
MAX_CHOICES = 10_000
MAX_STRING = 200
_MAXINT = 2**53

_COMMON = {"type", "nullable", "unique"}
_ALLOWED: dict[str, set[str]] = {
    "int": {"min", "max"},
    "float": {"min", "max", "decimals"},
    "bool": {"p_true"},
    "choice": {"values", "weights"},
    "sequence": {"start", "step", "template"},
    "date": {"start", "end", "after", "min_days", "max_days"},
    "datetime": {"start", "end"},
    "name": {"part"},
    "email": set(),
    "fk": {"table", "column"},
}


@dataclass(frozen=True)
class Column:
    """A validated column with normalized options."""

    name: str
    type: str
    nullable: float
    unique: bool
    options: Mapping[str, Any]


@dataclass(frozen=True)
class Table:
    """A validated table."""

    name: str
    rows: int
    columns: tuple[Column, ...]


@dataclass(frozen=True)
class Schema:
    """A validated schema; ``order`` is the topological generation order."""

    tables: tuple[Table, ...]
    order: tuple[str, ...]


def _s(value: object) -> str:
    return repr(value)[:40]


def _is_int(v: object) -> TypeGuard[int]:
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v: object) -> TypeGuard[int | float]:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _parse_date(v: object) -> date | None:
    if not isinstance(v, str) or len(v) > 10:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def _parse_dt(v: object) -> datetime | None:
    if not isinstance(v, str) or len(v) > 40:
        return None
    text = v[:-1] + "+00:00" if v.endswith("Z") else v
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0)


class _Ctx:
    def __init__(
        self,
        label: str,
        spec: Mapping[str, Any],
        rows: int,
        unique: bool,
        nullable: float,
        cname: str,
        table: str,
        earlier: Mapping[str, str],
        parsed: Mapping[str, tuple[int, Mapping[Any, Any]]],
        problems: list[str],
    ) -> None:
        self.label = label
        self.spec = spec
        self.rows = rows
        self.unique = unique
        self.nullable = nullable
        self.cname = cname
        self.table = table
        self.earlier = earlier
        self.parsed = parsed
        self.problems = problems

    def bad(self, msg: str) -> None:
        self.problems.append(f"{self.label}: {msg}")


def _t_int(c: _Ctx) -> dict[str, Any]:
    lo, hi = c.spec.get("min"), c.spec.get("max")
    if not (_is_int(lo) and _is_int(hi)) or abs(lo) > _MAXINT or abs(hi) > _MAXINT:
        c.bad("min and max must be integers within +-2**53")
        return {}
    if lo > hi:
        c.bad("min must not exceed max")
        return {}
    if c.unique and hi - lo + 1 < c.rows:
        c.bad("unique int domain is smaller than the number of rows")
    return {"min": lo, "max": hi}


def _t_float(c: _Ctx) -> dict[str, Any]:
    lo, hi = c.spec.get("min"), c.spec.get("max")
    dec = c.spec.get("decimals", 2)
    if not (_is_num(lo) and _is_num(hi)) or abs(lo) > 1e15 or abs(hi) > 1e15:
        c.bad("min and max must be finite numbers within +-1e15")
        return {}
    if lo > hi:
        c.bad("min must not exceed max")
    if not _is_int(dec) or not 0 <= dec <= 10:
        c.bad("decimals must be an integer from 0 to 10")
        return {}
    return {"min": float(lo), "max": float(hi), "decimals": dec}


def _t_bool(c: _Ctx) -> dict[str, Any]:
    p = c.spec.get("p_true", 0.5)
    if not _is_num(p) or not 0 <= p <= 1:
        c.bad("p_true must be a number in [0, 1]")
        return {}
    return {"p_true": float(p)}


def _t_choice(c: _Ctx) -> dict[str, Any]:
    vals = c.spec.get("values")
    if not isinstance(vals, (list, tuple)) or not 0 < len(vals) <= MAX_CHOICES:
        c.bad(f"values must be a list of 1 to {MAX_CHOICES} scalars")
        return {}
    for v in vals:
        ok = isinstance(v, (str, int, float, bool))
        if ok and isinstance(v, str) and len(v) > MAX_STRING:
            ok = False
        if ok and isinstance(v, float) and not math.isfinite(v):
            ok = False
        if not ok:
            c.bad("values must be short strings, numbers or booleans")
            return {}
    weights = c.spec.get("weights")
    if weights is not None:
        if (
            not isinstance(weights, (list, tuple))
            or len(weights) != len(vals)
            or not all(_is_num(w) and w >= 0 for w in weights)
            or sum(weights) <= 0
        ):
            c.bad("weights must match values in length, be non-negative and sum above 0")
            return {}
        weights = tuple(float(w) for w in weights)
    if c.unique and len(vals) < c.rows:
        c.bad("unique choice has fewer values than rows")
    return {"values": tuple(vals), "weights": weights}


def _t_sequence(c: _Ctx) -> dict[str, Any]:
    start, step = c.spec.get("start", 1), c.spec.get("step", 1)
    if not (_is_int(start) and _is_int(step)) or abs(start) > _MAXINT or not 0 < abs(step) <= 10**6:
        c.bad("start must be an integer and step a non-zero integer")
        return {}
    tpl = c.spec.get("template")
    if tpl is not None:
        if not isinstance(tpl, str) or len(tpl) > MAX_TEMPLATE:
            c.bad("template must be a short string")
            return {}
        rest = PLACEHOLDER.sub("", tpl)
        if "{" in rest or "}" in rest:
            c.bad("template may only contain {seq} or {seq:0Nd} placeholders (N from 1 to 20)")
            return {}
    return {"start": start, "step": step, "template": tpl}


def _t_date(c: _Ctx) -> dict[str, Any]:
    s = c.spec
    if "after" in s:
        if "start" in s or "end" in s:
            c.bad("after cannot be combined with start or end")
        base, mn, mx = s["after"], s.get("min_days"), s.get("max_days")
        if not isinstance(base, str) or c.earlier.get(base) != "date":
            c.bad("after must name an earlier date column of the same table")
        if not (_is_int(mn) and _is_int(mx)) or not 0 <= mn <= mx <= 36_500:
            c.bad("min_days and max_days must be integers with 0 <= min_days <= max_days")
        return {"after": base, "min_days": mn, "max_days": mx}
    start, end = _parse_date(s.get("start")), _parse_date(s.get("end"))
    if start is None or end is None:
        c.bad("start and end must be ISO dates (YYYY-MM-DD)")
        return {}
    if end < start:
        c.bad("end precedes start")
    elif c.unique and (end - start).days + 1 < c.rows:
        c.bad("unique date domain is smaller than the number of rows")
    return {"after": None, "start": start, "end": end}


def _t_datetime(c: _Ctx) -> dict[str, Any]:
    start, end = _parse_dt(c.spec.get("start")), _parse_dt(c.spec.get("end"))
    if start is None or end is None:
        c.bad("start and end must be ISO datetimes")
        return {}
    if end < start:
        c.bad("end precedes start")
    elif c.unique and int((end - start).total_seconds()) + 1 < c.rows:
        c.bad("unique datetime domain is smaller than the number of rows")
    return {"start": start, "end": end}


def _t_name(c: _Ctx) -> dict[str, Any]:
    part = c.spec.get("part", "full")
    if part not in ("first", "last", "full"):
        c.bad("part must be first, last or full")
        return {}
    size = {
        "first": len(FIRST_NAMES),
        "last": len(LAST_NAMES),
        "full": len(FIRST_NAMES) * len(LAST_NAMES),
    }[part]
    if c.unique and size < c.rows:
        c.bad("unique name domain is smaller than the number of rows")
    return {"part": part}


def _t_email(c: _Ctx) -> dict[str, Any]:
    return {}


def _t_fk(c: _Ctx) -> dict[str, Any]:
    tbl, col = c.spec.get("table"), c.spec.get("column")
    if not isinstance(tbl, str) or not isinstance(col, str):
        c.bad("fk needs string table and column")
        return {}
    if tbl not in c.parsed:
        c.bad(f"fk references unknown table {_s(tbl)}")
        return {}
    rrows, rcols = c.parsed[tbl]
    if col not in rcols:
        c.bad(f"fk references unknown column {_s(col)}")
        return {}
    if tbl == c.table:
        if c.nullable <= 0:
            c.bad("self-referencing fk must be nullable")
        if col == c.cname:
            c.bad("fk must not reference itself")
    elif rrows == 0:
        c.bad(f"fk references table {tbl} which has 0 rows")
    return {"table": tbl, "column": col}


_HANDLERS = {
    "int": _t_int,
    "float": _t_float,
    "bool": _t_bool,
    "choice": _t_choice,
    "sequence": _t_sequence,
    "date": _t_date,
    "datetime": _t_datetime,
    "name": _t_name,
    "email": _t_email,
    "fk": _t_fk,
}


def _column(
    table: str,
    cname: str,
    spec: Any,
    rows: int,
    earlier: Mapping[str, str],
    parsed: Mapping[str, tuple[int, Mapping[Any, Any]]],
    problems: list[str],
) -> Column | None:
    label = f"{table}.{cname}"
    n0 = len(problems)
    if not isinstance(spec, Mapping):
        problems.append(f"{label}: spec must be a mapping")
        return None
    typ = spec.get("type")
    if not isinstance(typ, str) or typ not in _ALLOWED:
        problems.append(f"{label}: unknown column type {_s(typ)}")
        return None
    extra = sorted(str(k)[:20] for k in spec if k not in _ALLOWED[typ] | _COMMON)
    if extra:
        problems.append(f"{label}: unknown option(s) {', '.join(extra)[:80]}")
    nullable = spec.get("nullable", 0)
    if not _is_num(nullable) or not 0 <= nullable <= 1:
        problems.append(f"{label}: nullable must be a number in [0, 1]")
        nullable = 0
    unique = spec.get("unique", False)
    if not isinstance(unique, bool):
        problems.append(f"{label}: unique must be a boolean")
        unique = False
    ctx = _Ctx(label, spec, rows, unique, float(nullable), cname, table, earlier, parsed, problems)
    options = _HANDLERS[typ](ctx)
    if len(problems) > n0:
        return None
    return Column(cname, typ, float(nullable), unique, options)


def _topo(names: list[str], deps: Mapping[str, set[str]]) -> tuple[list[str], list[str]]:
    remaining = {n: set(deps.get(n, ())) for n in names}
    order: list[str] = []
    while remaining:
        ready = sorted(n for n, d in remaining.items() if not d)
        if not ready:
            return order, sorted(remaining)
        order.append(ready[0])
        del remaining[ready[0]]
        for d in remaining.values():
            d.discard(ready[0])
    return order, []


def validate_schema(raw: Mapping[str, Any]) -> Schema:
    """Validate ``raw`` and return an immutable :class:`Schema`.

    Raises:
        SchemaError: with every problem found (code ``invalid_schema``), or code
            ``too_large`` when limits on tables or total rows are exceeded.
    """
    if (
        not isinstance(raw, Mapping)
        or not isinstance(raw.get("tables"), Mapping)
        or not raw["tables"]
    ):
        raise SchemaError(["schema must be a mapping with a non-empty 'tables' mapping"])
    traw = raw["tables"]
    if len(traw) > MAX_TABLES:
        raise SchemaError([f"at most {MAX_TABLES} tables are allowed"], "too_large")
    total = sum(
        t["rows"]
        for t in traw.values()
        if isinstance(t, Mapping) and _is_int(t.get("rows")) and t["rows"] > 0
    )
    if total > MAX_TOTAL_ROWS:
        raise SchemaError([f"at most {MAX_TOTAL_ROWS} rows in total are allowed"], "too_large")
    problems: list[str] = []
    parsed: dict[str, tuple[int, Mapping[Any, Any]]] = {}
    for name, t in traw.items():
        if not isinstance(name, str) or not NAME_RE.match(name):
            problems.append(f"invalid table name {_s(name)}")
            continue
        if not isinstance(t, Mapping):
            problems.append(f"{name}: table must be a mapping")
            continue
        rows, cols = t.get("rows"), t.get("columns")
        if not _is_int(rows) or rows < 0:
            problems.append(f"{name}: rows must be a non-negative integer")
            continue
        if not isinstance(cols, Mapping) or not 0 < len(cols) <= MAX_COLUMNS:
            problems.append(f"{name}: columns must be a mapping of 1 to {MAX_COLUMNS} columns")
            continue
        parsed[name] = (rows, cols)
    tables: list[Table] = []
    deps: dict[str, set[str]] = {}
    for tname, (rows, craw) in parsed.items():
        earlier: dict[str, str] = {}
        columns: list[Column] = []
        for cname, spec in craw.items():
            if not isinstance(cname, str) or not NAME_RE.match(cname):
                problems.append(f"{tname}: invalid column name {_s(cname)}")
                continue
            col = _column(tname, cname, spec, rows, earlier, parsed, problems)
            if isinstance(spec, Mapping) and isinstance(spec.get("type"), str):
                earlier[cname] = spec["type"]
            if col is not None:
                columns.append(col)
                if col.type == "fk" and col.options["table"] != tname:
                    deps.setdefault(tname, set()).add(col.options["table"])
        tables.append(Table(tname, rows, tuple(columns)))
    order, left = _topo([t.name for t in tables], deps)
    if left:
        problems.append(f"foreign key cycle between tables: {', '.join(left)}")
    if problems:
        raise SchemaError(problems)
    return Schema(tuple(tables), tuple(order))
