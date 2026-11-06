"""Deterministic generation of related tables."""

from __future__ import annotations

import hashlib
import logging
import math
import random
import re
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Any

from .errors import GenerationError, SchemaError
from .schema import PLACEHOLDER, Column, Schema, Table, validate_schema
from .words import FIRST_NAMES, LAST_NAMES

logger = logging.getLogger(__name__)

EMAIL_DOMAINS = ("example.com", "example.org", "example.net")
MAX_ATTEMPTS = 100

Value = str | int | float | bool | None
Row = dict[str, Value]
Draw = Callable[[Row, int], Value]


def _idx(rng: random.Random, n: int) -> int:
    return min(math.floor(rng.random() * n), n - 1)


def _int_in(rng: random.Random, lo: int, hi: int) -> int:
    return lo + _idx(rng, hi - lo + 1)


def _pick(rng: random.Random, weights: Sequence[float]) -> int:
    total = sum(weights)
    if total <= 0:
        raise GenerationError("no choice with a positive weight is left")
    x = rng.random() * total
    acc = 0.0
    for k, w in enumerate(weights):
        acc += w
        if x < acc:
            return k
    return max(k for k, w in enumerate(weights) if w > 0)


def _fold(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", ascii_text.lower())


def _retry(draw: Draw, unique: bool, label: str) -> Draw:
    if not unique:
        return draw
    seen: set[Value] = set()

    def g(row: Row, i: int) -> Value:
        for _ in range(MAX_ATTEMPTS):
            v = draw(row, i)
            if v is None:
                return None
            if v not in seen:
                seen.add(v)
                return v
        raise GenerationError(f"{label}: no unique value after {MAX_ATTEMPTS} draws")

    return g


def _unique_int(rng: random.Random, lo: int, hi: int) -> Draw:
    span = hi - lo + 1
    swap: dict[int, int] = {}
    used = [0]

    def g(row: Row, i: int) -> Value:
        k = used[0]
        used[0] += 1
        j = k + _idx(rng, span - k)
        vj = swap.get(j, j)
        swap[j] = swap.get(k, k)
        return lo + vj

    return g


def _unique_choice(rng: random.Random, vals: Sequence[Any], w: Sequence[float]) -> Draw:
    rem = list(range(len(vals)))

    def g(row: Row, i: int) -> Value:
        if not rem:
            raise GenerationError("unique choice is exhausted")
        k = _pick(rng, [w[j] for j in rem])
        value: Value = vals[rem.pop(k)]
        return value

    return g


def _make(
    table: Table,
    col: Column,
    rng: random.Random,
    data: Mapping[str, list[Row]],
    rows: list[Row],
) -> Draw:
    o = col.options
    t = col.type
    label = f"{table.name}.{col.name}"
    if t == "int":
        lo, hi = o["min"], o["max"]
        if col.unique:
            return _unique_int(rng, lo, hi)
        return lambda row, i: _int_in(rng, lo, hi)
    if t == "choice":
        vals = o["values"]
        w = o["weights"] or (1.0,) * len(vals)
        if col.unique:
            return _unique_choice(rng, vals, w)
        return lambda row, i: vals[_pick(rng, w)]
    if t == "sequence":
        start, step, tpl = o["start"], o["step"], o["template"]

        def seq(row: Row, i: int) -> Value:
            v = start + i * step
            if tpl is None:
                return int(v)
            return PLACEHOLDER.sub(
                lambda m: format(v, f"0{m.group(1)}d") if m.group(1) else str(v), tpl
            )

        return seq
    draw: Draw
    if t == "float":
        flo, fhi, dec = o["min"], o["max"], o["decimals"]
        draw = lambda row, i: round(flo + rng.random() * (fhi - flo), dec)  # noqa: E731
    elif t == "bool":
        p = o["p_true"]
        draw = lambda row, i: rng.random() < p  # noqa: E731
    elif t == "date":
        draw = _date_draw(rng, o)
    elif t == "datetime":
        dstart, dend = o["start"], o["end"]
        secs = int((dend - dstart).total_seconds())

        def dt(row: Row, i: int) -> Value:
            moment: datetime = dstart + timedelta(seconds=_int_in(rng, 0, secs))
            return moment.isoformat(timespec="seconds") + "Z"

        draw = dt
    elif t == "name":
        draw = _name_draw(rng, o["part"])
    elif t == "email":
        draw = _email_draw(rng, table, col.unique)
    else:
        draw = _fk_draw(rng, o, table, data, rows)
    return _retry(draw, col.unique, label)


def _date_draw(rng: random.Random, o: Mapping[str, Any]) -> Draw:
    if o["after"] is not None:
        base_col, mn, mx = o["after"], o["min_days"], o["max_days"]

        def after(row: Row, i: int) -> Value:
            base = row.get(base_col)
            if not isinstance(base, str):
                return None
            try:
                return (date.fromisoformat(base) + timedelta(days=_int_in(rng, mn, mx))).isoformat()
            except OverflowError as exc:
                raise GenerationError("date out of range") from exc

        return after
    ordinal = o["start"].toordinal()
    days = (o["end"] - o["start"]).days
    return lambda row, i: date.fromordinal(ordinal + _int_in(rng, 0, days)).isoformat()


def _name_draw(rng: random.Random, part: str) -> Draw:
    def g(row: Row, i: int) -> Value:
        if part == "first":
            return FIRST_NAMES[_idx(rng, len(FIRST_NAMES))]
        if part == "last":
            return LAST_NAMES[_idx(rng, len(LAST_NAMES))]
        first = FIRST_NAMES[_idx(rng, len(FIRST_NAMES))]
        return f"{first} {LAST_NAMES[_idx(rng, len(LAST_NAMES))]}"

    return g


def _email_draw(rng: random.Random, table: Table, unique: bool) -> Draw:
    name_cols = [c.name for c in table.columns if c.type == "name"]

    def g(row: Row, i: int) -> Value:
        domain = EMAIL_DOMAINS[_idx(rng, len(EMAIL_DOMAINS))]
        parts: list[str] = []
        for n in name_cols:
            v = row.get(n)
            if isinstance(v, str):
                parts.extend(_fold(p) for p in v.split())
        base = ".".join(p for p in parts if p)
        if not base:
            return f"user{_int_in(rng, 0, 999_999)}@{domain}"
        if unique:
            base = f"{base}{_int_in(rng, 0, 9999)}"
        return f"{base}@{domain}"

    return g


def _fk_draw(
    rng: random.Random,
    o: Mapping[str, Any],
    table: Table,
    data: Mapping[str, list[Row]],
    rows: list[Row],
) -> Draw:
    ref, rcol = o["table"], o["column"]
    selfref = ref == table.name
    pool: list[Value] = []
    pos = [0]

    def g(row: Row, i: int) -> Value:
        src = rows if selfref else data[ref]
        while pos[0] < len(src):
            v = src[pos[0]][rcol]
            pos[0] += 1
            if v is not None:
                pool.append(v)
        if not pool:
            if selfref:
                return None
            raise GenerationError(f"fk target {ref}.{rcol} has no values")
        return pool[_idx(rng, len(pool))]

    return g


def _gen_table(table: Table, seed: int, data: Mapping[str, list[Row]]) -> list[Row]:
    digest = hashlib.sha256(f"{seed}:{table.name}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))  # noqa: S311
    rows: list[Row] = []
    gens = [(c, _make(table, c, rng, data, rows)) for c in table.columns]
    for i in range(table.rows):
        row: Row = {}
        for c, g in gens:
            if c.nullable > 0 and rng.random() < c.nullable:
                row[c.name] = None
            else:
                row[c.name] = g(row, i)
        rows.append(row)
    logger.debug("generated table %s with %d rows", table.name, len(rows))
    return rows


def generate(
    schema: Schema | Mapping[str, Any], *, seed: int
) -> dict[str, list[dict[str, str | int | float | bool | None]]]:
    """Generate every table of ``schema`` deterministically from ``seed``.

    Each table has its own generator seeded from ``sha256(f"{seed}:{table}")``, so adding a
    table never changes the rows of the others. Tables are produced in foreign-key order.

    Raises:
        SchemaError: if ``seed`` is not an int or a raw schema is invalid.
        GenerationError: if a uniqueness constraint cannot be met.
    """
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SchemaError(["seed must be an int"])
    sch = schema if isinstance(schema, Schema) else validate_schema(schema)
    by_name = {t.name: t for t in sch.tables}
    data: dict[str, list[Row]] = {}
    for name in sch.order:
        data[name] = _gen_table(by_name[name], seed, data)
    return {t.name: data[t.name] for t in sch.tables}
