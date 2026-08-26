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

The numbers below measure the shipped artifact. A wheel from PyPI is the
LTO+PGO build the release workflow produces, so installing valgebra from the
index is enough; an editable `uv sync` against a `../valgebra` checkout produces
a debug build and understates valgebra by several times.

The interpreter is part of what is measured. A free-threaded build runs
single-threaded work slower, and by different factors for the two libraries, so
the figures below are from a standard GIL build and a comparison across builds
is not one:

```bash
uv venv /tmp/bench --python 3.14
VIRTUAL_ENV=/tmp/bench uv pip install "valgebra==0.0.8" "vtjson==2.3.0" \
  pytest pytest-benchmark
VIRTUAL_ENV=/tmp/bench uv pip install -e . --no-deps
/tmp/bench/bin/python -m pytest benches/bench_vtjson_compare.py \
  -o python_files="bench_*.py" --benchmark-min-rounds=200 \
  --benchmark-columns=mean,stddev --benchmark-sort=name
```

## Baseline

AMD Ryzen 7 PRO 7840U (Zen 4 "Phoenix", a 2023-era mobile part) under WSL2 on
Linux 6.18, CPython 3.14.7 standard build, valgebra 0.0.8 from PyPI, vtjson
2.3.0. Mean and standard deviation over at least two hundred rounds of a single
membership check on a passing value, lower is better:

| Family | valgebra | vtjson | valgebra faster by |
| --- | --- | --- | --- |
| Scalar (`int`) | 36.9 ± 21.3 ns | 919 ± 472 ns | 24.9x |
| Union (4 arms) | 74.9 ± 28.0 ns | 2.19 ± 1.40 us | 29.3x |
| Refinement (bounded int) | 101 ± 37 ns | 1.18 ± 0.62 us | 11.8x |
| Nested record + `[str, ...]` | 144 ± 42 ns | 3.40 ± 1.78 us | 23.7x |
| Format (regex) | 256 ± 151 ns | 1.16 ± 0.58 us | 4.5x |
| Deep nesting (12 levels) | 334 ± 121 ns | 7.36 ± 2.54 us | 22.1x |
| Record, 50 fields | 821 ± 320 ns | 11.1 ± 4.7 us | 13.6x |
| Mapping `{str: int}`, 50 entries | 875 ± 300 ns | 14.6 ± 5.5 us | 16.7x |
| Heterogeneous `{str: int, int: bool}` | 2.13 ± 1.11 us | 44.7 ± 14.7 us | 21.0x |
| `[int, ...]`, 10,000 elements | 46.8 ± 11.8 us | 1312 ± 150 us | 28.0x |
| Prefix+tail `[str, int, ...]` | 47.7 ± 13.3 us | 1335 ± 156 us | 28.0x |

valgebra is faster on every family. The spread is wide in relative terms — a
per-round standard deviation of a third is ordinary on a laptop under load — and
the **ratio** is the figure that travels, since both columns are measured in the
same rounds and absorb the same noise.

The gap widens with the number of elements checked: vtjson pays per-element
Python interpreter overhead, while valgebra crosses into Rust once per call and
walks the value there.

The **format** family is the narrowest at 4.5x, and it is the one place the two
libraries run the same engine. A pattern is matched by Python's `re` on both
sides, because the compatibility layer holds itself to `re`'s decisions:
valgebra's native `Regex` is a Rust engine whose dialect differs on patterns
both accept, so adopting it would change which strings a schema admits. The
narrow margin is that choice, not a limit of the walk.

## Honest limits

- These are a single machine class; re-run on your own hardware for absolute
  numbers. The ratios are what travel.
- vtjson's default `validate(schema, obj)` recompiles the schema on every call,
  which is slower still (for the 50-field record, ~270 us per call versus the
  ~12 us compile-once path measured above). The table uses vtjson's compile-once
  path, its best case, to keep the comparison fair.
- valgebra and vtjson reach the same decision here only for the constructs the
  compatibility layer supports; the differences ledger
  (`docs/vtjson-conformance.md`) records where valgebra deliberately decides
  differently.
- The comparison is the validation step only. It is not a claim that the two are
  interchangeable for every workflow.
