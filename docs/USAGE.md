# Usage

`synthetic_data` builds related tables from a declarative schema.

```python
import synthetic_data as sd

schema = sd.validate_schema({"tables": {"t": {"rows": 2, "columns": {"id": {"type": "sequence"}}}}})
print(sd.generate(schema, seed=1))
```

## Notes

- Column types: int, float, bool, choice, sequence, date, datetime, name, email, fk.
- Every table has its own random generator seeded from `sha256(f"{seed}:{table}")`, and all draws use `random()` only, so output is stable across Python versions.
- Limits: 100 tables, 200 columns per table, 1,000,000 rows in total (`too_large`).
- Sequence templates accept only `{seq}` and `{seq:0Nd}` (N from 1 to 20); they are parsed with a regular expression and never passed to `str.format`.
- Email addresses use the reserved domains example.com, example.org and example.net (RFC 2606).
- The bundled English and Spanish names are generic; any resemblance to real people is coincidental.
- Out of scope: learning from real data, other locales, SQL output, regex strings.
