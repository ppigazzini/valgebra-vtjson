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

The interpreter is part of what is measured, and its **build** is part of the
interpreter. A free-threaded build runs single-threaded work slower, and by
different factors for the two libraries, so the figures below are from a
standard GIL build and a comparison across builds is not one.

`--python 3.14` does not settle that. It resolves to whichever 3.14 is
installed, which on a machine carrying a free-threaded one is that — so confirm
the build rather than assuming it:

```bash
uv venv /tmp/bench --python 3.14
/tmp/bench/bin/python -c "import sysconfig; print(sysconfig.get_config_var('Py_GIL_DISABLED'))"
```

`0` is a GIL build and is what these figures were measured on; `1` is
free-threaded, and the numbers below do not describe it. Name an exact
interpreter — `--python cpython-3.14.7` — if the default resolves to the wrong
one.

```bash
VIRTUAL_ENV=/tmp/bench uv pip install "valgebra==0.0.9" "vtjson==2.3.0" \
  pytest pytest-benchmark
VIRTUAL_ENV=/tmp/bench uv pip install -e . --no-deps
/tmp/bench/bin/python -m pytest benches/bench_vtjson_compare.py \
  -o python_files="bench_*.py" --benchmark-min-rounds=200 \
  --benchmark-columns=mean,stddev --benchmark-sort=name
```

## Baseline

AMD Ryzen 7 PRO 7840U (Zen 4 "Phoenix", a 2023-era mobile part) under WSL2 on
Linux 6.18, CPython 3.14.7 standard build, valgebra 0.0.9 from PyPI, vtjson
2.3.0. Mean and standard deviation over at least two hundred rounds of a single
membership check on a passing value, lower is better:

| Family | valgebra | vtjson | valgebra faster by |
| --- | --- | --- | --- |
| Scalar (`int`) | 35 ± 10 ns | 820 ± 348 ns | 23.4x |
| Union (4 arms) | 67 ± 21 ns | 1.93 ± 1.39 us | 28.9x |
| Refinement (bounded int) | 91 ± 24 ns | 1.13 ± 0.39 us | 12.4x |
| Nested record + `[str, ...]` | 142 ± 36 ns | 2.99 ± 1.17 us | 21.1x |
| Format (regex) | 197 ± 64 ns | 1.01 ± 0.38 us | 5.1x |
| Deep nesting (12 levels) | 340 ± 116 ns | 6.44 ± 1.24 us | 18.9x |
| Record, 50 fields | 834 ± 242 ns | 10.7 ± 2.72 us | 12.8x |
| Mapping `{str: int}`, 50 entries | 885 ± 215 ns | 14.0 ± 3.35 us | 15.8x |
| Heterogeneous `{str: int, int: bool}` | 2.10 ± 0.59 us | 41.3 ± 11.1 us | 19.7x |
| `[int, ...]`, 10,000 elements | 45.3 ± 10.6 us | 1244 ± 109 us | 27.4x |
| Prefix+tail `[str, int, ...]` | 45.6 ± 10.3 us | 1217 ± 112 us | 26.7x |

valgebra is faster on every family. The spread is wide in relative terms — a
per-round standard deviation of a third is ordinary on a laptop under load — and
the **ratio** is the figure that travels, since both columns are measured in the
same rounds and absorb the same noise.

The gap widens with the number of elements checked: vtjson pays per-element
Python interpreter overhead, while valgebra crosses into Rust once per call and
walks the value there.

The **format** family is the narrowest at 5.1x, and it is the one place the two
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
  (`03-conformance.md`) records where valgebra deliberately decides
  differently.
- The comparison is the validation step only. It is not a claim that the two are
  interchangeable for every workflow.
