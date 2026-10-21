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
VIRTUAL_ENV=/tmp/bench uv pip install "valgebra==0.0.19" "vtjson==2.3.0" \
  "annotated-types>=0.8" pytest pytest-benchmark
VIRTUAL_ENV=/tmp/bench uv pip install -e . --no-deps
/tmp/bench/bin/python -m pytest benches/bench_vtjson_compare.py \
  -o python_files="bench_*.py" --benchmark-min-rounds=200 \
  --benchmark-columns=mean,stddev --benchmark-sort=name
```

## Baseline

AMD Ryzen 7 PRO 7840U (Zen 4 "Phoenix", a 2023-era mobile part) under WSL2 on
Linux 6.18, CPython 3.14.7 standard build, valgebra 0.0.19 from PyPI, vtjson
2.3.0. Mean and standard deviation over at least two hundred rounds of a single
membership check on a passing value, median of three runs, lower is better:

| Family | valgebra | vtjson | valgebra faster by |
| --- | --- | --- | --- |
| Scalar (`int`) | 40 ns ± 18 ns | 856 ns ± 424 ns | 21.6x |
| Union (4 arms) | 41 ns ± 17 ns | 2.01 us ± 1.20 us | 49.6x |
| Refinement (bounded int) | 77 ns ± 34 ns | 1.20 us ± 1.34 us | 15.6x |
| Nested record + `[str, ...]` | 97 ns ± 53 ns | 3.07 us ± 1.72 us | 31.7x |
| Format (regex) | 201 ns ± 74 ns | 1.11 us ± 734 ns | 5.6x |
| Deep nesting (12 levels) | 249 ns ± 85 ns | 6.80 us ± 3.00 us | 27.3x |
| Mapping `{str: int}`, 50 entries | 342 ns ± 134 ns | 14.76 us ± 5.57 us | 43.2x |
| Record, 50 fields | 499 ns ± 231 ns | 11.10 us ± 3.91 us | 22.2x |
| Heterogeneous `{str: int, int: bool}` | 1.05 us ± 388 ns | 43.34 us ± 12.77 us | 41.1x |
| `[int, ...]`, 10,000 elements | 10.63 us ± 3.78 us | 1349 us ± 316.45 us | 126.9x |
| Prefix+tail `[str, int, ...]` | 44.20 us ± 12.57 us | 1309 us ± 149.21 us | 29.6x |

valgebra is faster on every family. The spread is wide in relative terms — a
per-round standard deviation of a third is ordinary on a laptop under load — and
the **ratio** is the figure that travels, since both columns are measured in the
same rounds and absorb the same noise.

The gap widens with the number of elements checked: vtjson pays per-element
Python interpreter overhead, while valgebra crosses into Rust once per call and
walks the value there. It widens furthest where the element schema is the same
at every position — a homogeneous `[int, ...]` is one loop over one element
schema, where a prefix and a tail is a machine that reads a different schema at
the front.

The **format** family is the narrowest at 5.6x, and it is the one place the two
libraries run the same engine. A pattern is matched by Python's `re` on both
sides, because the compatibility layer holds itself to `re`'s decisions:
valgebra's native `Regex` is a Rust engine whose dialect differs on patterns
both accept, so adopting it would change which strings a schema admits. The
narrow margin is that choice, not a limit of the walk.

## Honest limits

- These are a single machine class; re-run on your own hardware for absolute
  numbers. The ratios are what travel.
- vtjson's default `validate(schema, obj)` recompiles the schema on every call,
  which is slower still (for the 50-field record, ~230 us per call versus the
  ~11 us compile-once path measured above). The table uses vtjson's compile-once
  path, its best case, to keep the comparison fair.
- valgebra and vtjson reach the same decision here only for the constructs the
  compatibility layer supports; the differences ledger
  (`03-conformance.md`) records where valgebra deliberately decides
  differently.
- The comparison is the validation step only. It is not a claim that the two are
  interchangeable for every workflow.
