from __future__ import annotations

import copy
import io
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import pytest

import synthetic_data as sd
from synthetic_data.words import FIRST_NAMES, LAST_NAMES

SCHEMA: dict[str, Any] = {
    "tables": {
        "orders": {
            "rows": 20,
            "columns": {
                "id": {"type": "sequence", "start": 1, "template": "INV-{seq:05d}"},
                "customer_id": {"type": "fk", "table": "customers", "column": "id"},
                "total": {"type": "float", "min": 1, "max": 100, "decimals": 2},
                "paid": {"type": "bool", "p_true": 0.5},
            },
        },
        "customers": {
            "rows": 10,
            "columns": {
                "id": {"type": "int", "min": 1, "max": 10, "unique": True},
                "name": {"type": "name", "part": "full"},
                "email": {"type": "email", "unique": True},
                "signup": {
                    "type": "date",
                    "start": "2024-01-01",
                    "end": "2024-12-31",
                    "nullable": 0.3,
                },
                "ship": {"type": "date", "after": "signup", "min_days": 1, "max_days": 30},
                "manager_id": {"type": "fk", "table": "customers", "column": "id", "nullable": 0.5},
                "tier": {"type": "choice", "values": ["a", "b"], "weights": [1, 3]},
                "seen": {
                    "type": "datetime",
                    "start": "2024-01-01T00:00:00",
                    "end": "2024-01-02T00:00:00Z",
                },
            },
        },
    }
}


def one(spec: Any, rows: int = 3) -> dict[str, Any]:
    return {"tables": {"t": {"rows": rows, "columns": {"c": spec}}}}


def col(spec: Any, rows: int = 3, seed: int = 1) -> list[Any]:
    return [r["c"] for r in sd.generate(one(spec, rows), seed=seed)["t"]]


def test_determinism_and_types() -> None:
    a = sd.generate(SCHEMA, seed=1)
    assert a == sd.generate(SCHEMA, seed=1)
    assert a != sd.generate(SCHEMA, seed=2)
    assert json.loads(json.dumps(a)) == a
    assert list(a) == ["orders", "customers"]
    assert a["orders"][0]["id"] == "INV-00001"


def test_adding_table_keeps_existing_rows() -> None:
    bigger = copy.deepcopy(SCHEMA)
    bigger["tables"]["aaa"] = {"rows": 4, "columns": {"x": {"type": "int", "min": 0, "max": 9}}}
    a, b = sd.generate(SCHEMA, seed=1), sd.generate(bigger, seed=1)
    assert a["orders"] == b["orders"]
    assert a["customers"] == b["customers"]


def test_foreign_keys_exist() -> None:
    data = sd.generate(SCHEMA, seed=3)
    ids = {r["id"] for r in data["customers"]}
    assert all(r["customer_id"] in ids for r in data["orders"])
    assert data["customers"][0]["manager_id"] is None
    assert all(r["manager_id"] is None or r["manager_id"] in ids for r in data["customers"])
    assert sd.validate_schema(SCHEMA).order == ("customers", "orders")


def test_fk_cycle_names_both_tables() -> None:
    raw = {
        "tables": {
            "orders": {
                "rows": 1,
                "columns": {"c": {"type": "fk", "table": "customers", "column": "id"}},
            },
            "customers": {
                "rows": 1,
                "columns": {
                    "id": {"type": "sequence"},
                    "o": {"type": "fk", "table": "orders", "column": "c"},
                },
            },
        }
    }
    with pytest.raises(sd.SchemaError) as ei:
        sd.validate_schema(raw)
    assert ei.value.code == "invalid_schema"
    assert "orders" in str(ei.value)
    assert "customers" in str(ei.value)


def test_self_fk_and_empty_target() -> None:
    spec = {"type": "fk", "table": "t", "column": "id"}
    raw = {"tables": {"t": {"rows": 2, "columns": {"id": {"type": "sequence"}, "m": spec}}}}
    with pytest.raises(sd.SchemaError) as ei:
        sd.validate_schema(raw)
    assert ei.value.code == "invalid_schema"
    empty = {
        "tables": {
            "a": {"rows": 0, "columns": {"id": {"type": "sequence"}}},
            "b": {"rows": 2, "columns": {"f": {"type": "fk", "table": "a", "column": "id"}}},
        }
    }
    with pytest.raises(sd.SchemaError) as ei2:
        sd.validate_schema(empty)
    assert ei2.value.code == "invalid_schema"
    assert sd.generate(
        empty["tables"]["a"] and {"tables": {"a": empty["tables"]["a"]}}, seed=1
    ) == {"a": []}


def test_unique_int_domain() -> None:
    spec = {"type": "int", "min": 1, "max": 3, "unique": True}
    with pytest.raises(sd.SchemaError) as ei:
        sd.generate(one(spec, 4), seed=1)
    assert ei.value.code == "invalid_schema"
    assert set(col(spec, 3)) == {1, 2, 3}


def test_nullable() -> None:
    spec = {"type": "int", "min": 1, "max": 5, "nullable": 0.25}
    nulls = sum(v is None for v in col(spec, 1000, seed=7))
    assert 200 <= nulls <= 300
    assert all(v is not None for v in col({**spec, "nullable": 0}, 200, seed=7))
    assert all(v is None for v in col({**spec, "nullable": 1}, 200, seed=7))


def test_date_after() -> None:
    data = sd.generate(SCHEMA, seed=5)["customers"]
    for r in data:
        if r["signup"] is None:
            assert r["ship"] is None
        else:
            delta = date.fromisoformat(r["ship"]) - date.fromisoformat(r["signup"])
            assert 1 <= delta.days <= 30


def test_names_emails() -> None:
    rows = sd.generate(SCHEMA, seed=9)["customers"]
    for r in rows:
        assert re.fullmatch(r"[a-z0-9.]+@example\.(com|org|net)", r["email"])
        first, last = r["name"].split(" ")
        assert first in FIRST_NAMES
        assert last in LAST_NAMES
    parts = {
        "f": {"type": "name", "part": "first"},
        "l": {"type": "name", "part": "last"},
        "e": {"type": "email"},
    }
    out = sd.generate({"tables": {"t": {"rows": 5, "columns": parts}}}, seed=2)["t"]
    assert all(re.fullmatch(r"[a-z0-9.]+@example\.(com|org|net)", r["e"]) for r in out)
    assert all(r["f"] in FIRST_NAMES and r["l"] in LAST_NAMES for r in out)
    anon = col({"type": "email"}, 3)
    assert all(v.startswith("user") for v in anon)


@pytest.mark.parametrize("tpl", ["{seq.__class__}", "{seq!r}", "{seq:021d}", "{{seq}}"])
def test_bad_templates(tpl: str) -> None:
    with pytest.raises(sd.SchemaError):
        sd.validate_schema(one({"type": "sequence", "template": tpl}))


def test_sequences() -> None:
    assert col({"type": "sequence", "start": 1, "template": "INV-{seq:05d}"}, 2) == [
        "INV-00001",
        "INV-00002",
    ]
    assert col({"type": "sequence", "start": 10, "step": -2}) == [10, 8, 6]
    assert col({"type": "sequence", "template": "a{seq}-{seq}"}, 2) == ["a1-1", "a2-2"]


def test_every_type_and_unique_variants() -> None:
    cols: dict[str, Any] = {
        "f": {"type": "float", "min": 0, "max": 1, "decimals": 0},
        "uf": {"type": "float", "min": 0, "max": 1000, "unique": True},
        "ud": {"type": "date", "start": "2024-01-01", "end": "2024-12-31", "unique": True},
        "udt": {
            "type": "datetime",
            "start": "2024-01-01T00:00:00+00:00",
            "end": "2024-06-01T00:00:00",
            "unique": True,
        },
        "un": {"type": "name", "part": "first", "unique": True},
        "uc": {"type": "choice", "values": [1, 2, 3, 4, 5, 6], "unique": True},
        "uw": {"type": "choice", "values": ["x", "y"], "weights": [0, 1]},
    }
    out = sd.generate({"tables": {"t": {"rows": 6, "columns": cols}}}, seed=4)["t"]
    assert all(r["f"] in (0.0, 1.0) for r in out)
    assert len({r["uf"] for r in out}) == 6
    assert len({r["ud"] for r in out}) == 6
    assert all(re.fullmatch(r"2024-\d\d-\d\dT\d\d:\d\d:\d\dZ", r["udt"]) for r in out)
    assert len({r["un"] for r in out}) == 6
    assert {r["uc"] for r in out} == {1, 2, 3, 4, 5, 6}
    assert {r["uw"] for r in out} == {"y"}
    assert sd.generate({"tables": {"t": {"rows": 0, "columns": cols}}}, seed=1) == {"t": []}


def test_unique_email_and_fk() -> None:
    raw = {
        "tables": {
            "a": {"rows": 5, "columns": {"id": {"type": "sequence"}}},
            "b": {
                "rows": 5,
                "columns": {
                    "n": {"type": "name"},
                    "e": {"type": "email", "unique": True},
                    "f": {"type": "fk", "table": "a", "column": "id", "unique": True},
                },
            },
        }
    }
    rows = sd.generate(raw, seed=1)["b"]
    assert len({r["e"] for r in rows}) == 5
    assert len({r["f"] for r in rows}) == 5


def test_generation_error_on_impossible_unique() -> None:
    with pytest.raises(sd.GenerationError) as ei:
        sd.generate(one({"type": "bool", "unique": True}, 3), seed=1)
    assert ei.value.code == "generation_failed"
    assert isinstance(ei.value, sd.SyntheticDataError)
    with pytest.raises(sd.GenerationError):
        sd.generate(
            one({"type": "choice", "values": [1, 2], "weights": [1, 0], "unique": True}, 2), seed=1
        )


def test_fk_to_all_null_column_fails() -> None:
    raw = {
        "tables": {
            "a": {"rows": 2, "columns": {"id": {"type": "int", "min": 1, "max": 2, "nullable": 1}}},
            "b": {"rows": 1, "columns": {"f": {"type": "fk", "table": "a", "column": "id"}}},
        }
    }
    with pytest.raises(sd.GenerationError):
        sd.generate(raw, seed=1)


def test_date_overflow() -> None:
    raw = one(
        {"type": "date", "start": "9999-12-31", "end": "9999-12-31"},
    )
    raw["tables"]["t"]["columns"]["d"] = {
        "type": "date",
        "after": "c",
        "min_days": 1,
        "max_days": 2,
    }
    with pytest.raises(sd.GenerationError):
        sd.generate(raw, seed=1)


def test_rounding_and_weights() -> None:
    vals = col({"type": "float", "min": 0, "max": 1, "decimals": 3}, 50)
    assert all(v == round(v, 3) for v in vals)
    assert set(col({"type": "choice", "values": ["x", "y"], "weights": [0, 1]}, 20)) == {"y"}
    assert set(col({"type": "bool", "p_true": 1}, 5)) == {True}


@pytest.mark.parametrize(
    "spec",
    [
        "notamapping",
        {"type": "nope"},
        {"type": "int", "min": 5, "max": 1},
        {"type": "int", "min": "a", "max": 2},
        {"type": "float", "min": 0, "max": 1, "decimals": 11},
        {"type": "float", "min": 2, "max": 1},
        {"type": "float", "min": "x", "max": 1},
        {"type": "bool", "p_true": 2},
        {"type": "choice", "values": []},
        {"type": "choice", "values": [[1]]},
        {"type": "choice", "values": [1, 2], "weights": [1]},
        {"type": "choice", "values": [1, 2], "weights": [0, 0]},
        {"type": "choice", "values": [1, 2], "unique": True},
        {"type": "sequence", "step": 0},
        {"type": "sequence", "template": 5},
        {"type": "date", "start": "2024-02-01", "end": "2024-01-01"},
        {"type": "date", "start": "bad", "end": "2024-01-01"},
        {"type": "date", "start": "2024-01-01", "end": "2024-01-02", "unique": True},
        {"type": "date", "after": "missing", "min_days": 1, "max_days": 2},
        {"type": "date", "after": "c", "start": "2024-01-01", "min_days": 3, "max_days": 2},
        {"type": "datetime", "start": "2024-01-02T00:00:00", "end": "2024-01-01T00:00:00"},
        {"type": "datetime", "start": "nope", "end": "2024-01-01T00:00:00"},
        {"type": "name", "part": "middle"},
        {"type": "name", "part": "first", "unique": True},
        {"type": "fk", "table": "zzz", "column": "id"},
        {"type": "fk", "table": "t", "column": "zzz"},
        {"type": "fk", "table": 1, "column": "id"},
        {"type": "int", "min": 1, "max": 2, "nullable": 2},
        {"type": "int", "min": 1, "max": 2, "unique": "yes"},
        {"type": "int", "min": 1, "max": 2, "bogus": 1},
    ],
)
def test_bad_columns(spec: Any) -> None:
    rows = 100 if isinstance(spec, dict) and spec.get("unique") is True else 3
    if isinstance(spec, dict) and spec.get("type") == "date" and spec.get("unique"):
        rows = 3
    with pytest.raises(sd.SchemaError) as ei:
        sd.validate_schema(one(spec, rows))
    assert ei.value.code == "invalid_schema"
    assert len(str(ei.value)) <= 200


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {},
        {"tables": {}},
        {"tables": {"Bad": {"rows": 1, "columns": {"c": {"type": "bool"}}}}},
        {"tables": {"t": 5}},
        {"tables": {"t": {"rows": -1, "columns": {"c": {"type": "bool"}}}}},
        {"tables": {"t": {"rows": 1, "columns": {}}}},
        {"tables": {"t": {"rows": 1, "columns": {"Bad": {"type": "bool"}}}}},
    ],
)
def test_bad_structure(raw: Any) -> None:
    with pytest.raises(sd.SchemaError):
        sd.validate_schema(raw)


def test_problems_are_collected() -> None:
    raw = {
        "tables": {
            "t": {"rows": 1, "columns": {"a": {"type": "nope"}, "b": {"type": "int"}}},
        }
    }
    with pytest.raises(sd.SchemaError) as ei:
        sd.validate_schema(raw)
    assert len(ei.value.problems) == 2


def test_too_large() -> None:
    big = {"tables": {"a": {"rows": 1_000_001, "columns": {"c": {"type": "bool"}}}}}
    with pytest.raises(sd.SchemaError) as ei:
        sd.validate_schema(big)
    assert ei.value.code == "too_large"
    many = {
        "tables": {f"t{i}": {"rows": 0, "columns": {"c": {"type": "bool"}}} for i in range(101)}
    }
    with pytest.raises(sd.SchemaError) as ei2:
        sd.validate_schema(many)
    assert ei2.value.code == "too_large"


def test_seed_must_be_int() -> None:
    with pytest.raises(sd.SchemaError):
        sd.generate(SCHEMA, seed=True)


ROWS = [
    {"id": 1, "name": "Ana, Pérez", "ok": True, "x": None},
    {"id": 2, "name": "Bo", "ok": False, "x": 1.5},
]


def test_csv_golden() -> None:
    buf = io.StringIO()
    assert sd.to_csv(ROWS, buf) == 2
    assert buf.getvalue() == 'id,name,ok,x\n1,"Ana, Pérez",True,\n2,Bo,False,1.5\n'
    empty = io.StringIO()
    assert sd.to_csv([], empty, ["a", "b"]) == 0
    assert empty.getvalue() == "a,b\n"
    nothing = io.StringIO()
    assert sd.to_csv([], nothing) == 0
    assert nothing.getvalue() == ""


def test_jsonl_golden() -> None:
    buf = io.StringIO()
    assert sd.to_jsonl(ROWS, buf) == 2
    assert buf.getvalue() == (
        '{"id": 1, "name": "Ana, Pérez", "ok": true, "x": null}\n'
        '{"id": 2, "name": "Bo", "ok": false, "x": 1.5}\n'
    )


def test_write_all(tmp_path: Path) -> None:
    schema = sd.validate_schema(
        {"tables": {"e": {"rows": 0, "columns": {"a": {"type": "bool"}, "b": {"type": "bool"}}}}}
    )
    paths = sd.write_all({"a": [{"x": 1}], "e": []}, tmp_path / "out", "csv", schema)
    assert [p.name for p in paths] == ["a.csv", "e.csv"]
    assert paths[0].read_text(encoding="utf-8") == "x\n1\n"
    assert paths[1].read_text(encoding="utf-8") == "a,b\n"
    jl = sd.write_all({"a": [{"x": 1}]}, tmp_path, "jsonl")
    assert jl[0].read_text(encoding="utf-8") == '{"x": 1}\n'
    with pytest.raises(sd.SchemaError):
        sd.write_all({"a": []}, tmp_path, "xml")  # type: ignore[arg-type]
    with pytest.raises(sd.SchemaError):
        sd.write_all({"../x": []}, tmp_path, "csv")


def test_version() -> None:
    assert sd.__version__ == "0.1.0"
