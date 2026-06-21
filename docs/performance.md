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

The numbers below measure the shipped artifact, so build valgebra's LTO+PGO
release wheel and install it over the editable build before running — an editable
`uv sync` produces a debug build and understates valgebra. From a sibling
`../valgebra` checkout (`rustup component add llvm-tools` once, for the profile
merge):

```bash
uv sync --group bench
py=$(uv run --no-sync --group bench python -c 'import sys; print(sys.executable)')
(cd ../valgebra && PYO3_PYTHON="$py" \
  maturin build --release --pgo --out dist --interpreter "$py")
uv pip install --no-deps --reinstall ../valgebra/dist/valgebra-*.whl
uv run --no-sync --group bench pytest benches/bench_vtjson_compare.py \
  --benchmark-group-by=group
```

## Baseline

Machine class: AMD Ryzen 7 PRO 7840U (Zen 4 "Phoenix", up to 5.1 GHz, a 2023-era
mobile part) under WSL2 on Linux 6.18. CPython 3.14.6, vtjson 2.3.0, valgebra
built release with fat LTO and profile-guided optimization — the same optimized
wheel the release workflow ships, not an editable debug build. Per-call median on
a passing value, lower is better:

Eleven construct families, per-call median on a passing value, valgebra faster by
the factor shown. The ratio is the durable figure; absolute times move with the
machine and its load.

| Family | speedup | Family | speedup |
| --- | --- | --- | --- |
| Scalar (`int`) | ~26x | Deep nesting (12 levels) | ~21x |
| Closed record, 50 fields | ~14x | Union (4 arms) | ~29x |
| Mapping `{str: int}`, 50 entries | ~17x | Refinement (bounded int) | ~4x |
| `[int, ...]`, 10,000 elements | ~28x | Format (regex) | ~5x |
| Nested record + `[str, ...]` | ~23x | **Prefix+tail `[str, int, ...]`** | ~28x |
| **Heterogeneous `{str: int, int: bool}`** | ~21x | | |

valgebra is decisively faster on **every** family — none is a regression. The
two boldface families are the constructs valgebra grew a sequence-regex node and
a keyed-default mapping node for; both validate ~21–28x faster than vtjson. The
gap widens with the number of elements checked: vtjson pays per-element Python
interpreter overhead, while valgebra crosses into Rust once per call and walks
the value there. The thinnest margins are the refinement and format families
(~4–5x), where per-call dispatch or an identical `re` engine dominates — the
optimization frontier.

## Honest limits

- These are a single machine class; re-run on your own hardware for absolute
  numbers. The ratios are what travel.
- vtjson's default `validate(schema, obj)` recompiles the schema on every call,
  which is slower still (for the 50-field record, ~270 us per call versus the
  ~12 us compile-once path measured above). The table uses vtjson's compile-once
  path, its best case, to keep the comparison fair.
- valgebra and vtjson reach the same decision here only for the constructs the
  compatibility layer supports; the differences ledger
  (`docs/migrating-from-vtjson.md`) records where valgebra deliberately decides
  differently.
- The comparison is the validation step only. It is not a claim that the two are
  interchangeable for every workflow.
