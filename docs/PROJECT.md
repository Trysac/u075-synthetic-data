# Project record

## Objective

Seeded synthetic tabular data from a declarative schema: ten column types, uniqueness, nullability, foreign keys across tables and CSV or JSONL export

## Scope

- In scope: the public API documented in [README.md](../README.md), typed and tested.
- Out of scope: anything that needs runtime dependencies or I/O without an accepted ADR.

## Timeline

| Date | Event |
|---|---|
| 2026 | Repository created from the factory utility template. |

## Effort metrics

Measured values only; a value that has not been measured stays "pending measurement".

| Metric | Value |
|---|---|
| Tokens (input / output) | 167140 / 307223 |
| Hours (human) | pending measurement |
| Cost (USD) | 1.6059 |

## Factory run u075 (measured from API usage)

| Phase | Model | Batch | Input | Output | Cache write | Cache read | Cost (USD) |
|---|---|---|---|---|---|---|---|
| generation | claude-sonnet-5-5 | yes | 2169 | 128000 | 0 | 4246 | 0.6426 |
| generation | claude-sonnet-5-5 | yes | 2169 | 128000 | 0 | 4246 | 0.6426 |
| generation | claude-sonnet-5-5 | yes | 2169 | 46432 | 0 | 4246 | 0.2348 |
| docs | claude-haiku-5-5 | no | 147895 | 4791 | 0 | 0 | 0.0859 |

Total: $1.6059. Prices: Anthropic list prices.
