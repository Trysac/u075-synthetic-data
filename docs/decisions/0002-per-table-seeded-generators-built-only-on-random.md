# Per-table seeded generators built only on random()

Status: accepted (generated, pending human review)

## Context

Generated fixtures must be reproducible across Python versions and machines, and adding a table to a schema must not change the data of existing tables. Python only guarantees the random() sequence of random.Random across versions, not randrange, choice or shuffle, and the built-in hash() is salted per process.

## Decision

Each table gets its own random.Random seeded from the first 8 bytes of sha256(f'{seed}:{table}'). Every draw (integers, weighted choices, Fisher-Yates without replacement, dates) is derived from rng.random() alone. Tables are generated in foreign-key order with ties by name, and results are returned in declared order. Sequence templates are parsed with a strict regular expression and never passed to str.format. The bundled word lists live in a Python module.

## Consequences

Output is stable across Python versions and independent between tables. Uniqueness for floats, dates, datetimes, names, emails and foreign keys relies on bounded retries (100 draws) and can raise GenerationError. The implementation needs more code than randrange or shuffle would.
