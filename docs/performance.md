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

| Shape | valgebra (compat) | vtjson 2.3.0 | speedup |
| --- | --- | --- | --- |
| Closed record, 50 int fields | 3.2 us | 21.9 us | ~6.8x |
| Mapping `{str: int}`, 50 entries | 0.77 us | 28.0 us | ~36x |
| Nested record + `[str, ...]` | 0.47 us | 7.9 us | ~17x |
| `[int, ...]`, 10,000 elements | 56 us | 2,380 us | ~42x |

The gap widens with the number of elements checked: vtjson pays per-element
Python interpreter overhead, while valgebra crosses into Rust once per call and
walks the value there. On the small nested record the speedup is already an
order of magnitude; on the large array it is over 40x.

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
