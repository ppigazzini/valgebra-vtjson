# Performance: vtjson versus valgebra

The compatibility layer translates a vtjson-style schema onto valgebra's Rust
core. The same schema therefore validates far faster than under pure-Python
vtjson, while reaching the same accept or reject decision (proven by the
differential suite). This page records that speedup honestly.

## Method

`benches/bench_vtjson_compare.py` runs the same vtjson schema through both
libraries and times a single membership check on a passing value. Both compile
the schema once:

- **vtjson**: `vtjson.compile(schema)`, then `vtjson.validate(compiled, obj)` —
  its compile-once path, no recompilation per call.
- **valgebra**: `vtjson_compat.compile(schema)`, then `is_valid(obj)`.

Both check membership without coercion, so the comparison is like-for-like. The
shapes are the same Python value in both columns, since both libraries read the
implicit forms identically.

Run it with:

```bash
uv sync --group bench
uv run --group bench pytest benches/bench_vtjson_compare.py \
  --benchmark-group-by=group
```

## Baseline

Machine class: Intel Core i7-3770K (Ivy Bridge, 3.5 GHz, a 2012-era desktop
part) under WSL2 on Linux 6.18. CPython 3.14.5, vtjson 2.3.0, valgebra built
release (fat LTO). Per-call median on a passing value, lower is better:

Eleven construct families, per-call median on a passing value, valgebra faster by
the factor shown. The ratio is the durable figure; absolute times move with the
machine and its load.

| Family | speedup | Family | speedup |
| --- | --- | --- | --- |
| Scalar (`int`) | ~26x | Deep nesting (12 levels) | ~10x |
| Closed record, 50 fields | ~6x | Union (4 arms) | ~33x |
| Mapping `{str: int}`, 50 entries | ~12x | Refinement (bounded int) | ~5x |
| `[int, ...]`, 10,000 elements | ~20x | Format (regex) | ~6x |
| Nested record + `[str, ...]` | ~15x | **Prefix+tail `[str, int, ...]`** | ~20x |
| **Heterogeneous `{str: int, int: bool}`** | ~18x | | |

valgebra is decisively faster on **every** family — none is a regression. The
two boldface families are the constructs valgebra grew a sequence-regex node and
a keyed-default mapping node for; both validate ~18–20x faster than vtjson. The
gap widens with the number of elements checked: vtjson pays per-element Python
interpreter overhead, while valgebra crosses into Rust once per call and walks
the value there. The thinnest margins are the refinement, format, and record
families (~5–6x), where per-call dispatch or an identical `re` engine dominates —
the optimization frontier.

## Honest limits

- These are a single machine class; re-run on your own hardware for absolute
  numbers. The ratios are what travel.
- vtjson's default `validate(schema, obj)` recompiles the schema on every call,
  which is slower still (for the 50-field record, ~32 us per call versus the
  ~22 us compile-once path measured above). The table uses vtjson's compile-once
  path, its best case, to keep the comparison fair.
- valgebra and vtjson reach the same decision here only for the constructs the
  compatibility layer supports; the differences ledger
  (`docs/migrating-from-vtjson.md`) records where valgebra deliberately decides
  differently.
- The comparison is the validation step only. It is not a claim that the two are
  interchangeable for every workflow.
