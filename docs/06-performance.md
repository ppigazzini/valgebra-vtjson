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

Every figure is measured on the newest release the classifiers claim, so that
two readings compare: one wheel reads a family slower on one release and faster on
the next. `tests/test_performance_page.py` holds the page, its command and the
lane that smoke-runs the benchmark to that release.

`--python 3.15` does not settle the build. It resolves to whichever 3.15 is
installed, which on a machine carrying a free-threaded one is that — so confirm
the build rather than assuming it:

```bash
uv venv /tmp/bench --python 3.15
/tmp/bench/bin/python -c "import sysconfig; print(sysconfig.get_config_var('Py_GIL_DISABLED'))"
```

`0` is a GIL build and is what these figures were measured on; `1` is
free-threaded, and the numbers below do not describe it. Name an exact
interpreter — `--python cpython-3.15.2` — if the default resolves to the wrong
one.

```bash
VIRTUAL_ENV=/tmp/bench uv pip install "valgebra==0.0.26" "vtjson==2.3.0" \
  "annotated-types>=0.8" pytest pytest-benchmark
VIRTUAL_ENV=/tmp/bench uv pip install -e . --no-deps
/tmp/bench/bin/python -m pytest benches/bench_vtjson_compare.py \
  -o python_files="bench_*.py" --benchmark-min-rounds=200 \
  --benchmark-columns=mean,stddev --benchmark-sort=name
```

## Baseline

AMD Ryzen 7 PRO 7840U (Zen 4 "Phoenix", a 2023-era mobile part) under WSL2 on
Linux 6.18, CPython 3.15.2 standard build, valgebra 0.0.26 from PyPI, vtjson
2.3.0. Mean and standard deviation over at least two hundred rounds of a single
membership check on a passing value, median of three runs, lower is better:

| Family | valgebra | vtjson | valgebra faster by |
| --- | --- | --- | --- |
| Scalar (`int`) | 32 ns ± 13 ns | 850 ns ± 553 ns | 26.7x |
| Union (4 arms) | 39 ns ± 20 ns | 1.97 us ± 1.03 us | 50.6x |
| Refinement (bounded int) | 78 ns ± 31 ns | 1.08 us ± 657 ns | 13.9x |
| Nested record + `[str, ...]` | 95 ns ± 44 ns | 3.21 us ± 4.84 us | 33.7x |
| Mapping `{str: int}`, 50 entries | 245 ns ± 146 ns | 15.12 us ± 6.37 us | 61.7x |
| Deep nesting (12 levels) | 259 ns ± 174 ns | 7.04 us ± 3.59 us | 27.1x |
| Format (regex) | 297 ns ± 233 ns | 1.06 us ± 673 ns | 3.6x |
| Record, 50 fields | 470 ns ± 433 ns | 11.98 us ± 5.46 us | 25.5x |
| Heterogeneous `{str: int, int: bool}` | 721 ns ± 349 ns | 45.54 us ± 17.73 us | 63.2x |
| `[int, ...]`, 10,000 elements | 15.49 us ± 6.27 us | 1314 us ± 181.52 us | 84.8x |
| Prefix+tail `[str, int, ...]` | 46.43 us ± 17.23 us | 1340 us ± 225.46 us | 28.9x |

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

The **format** family is the narrowest at 3.6x, and it is the one place the two
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
  ~12 us compile-once path measured above). The table uses vtjson's compile-once
  path, its best case, to keep the comparison fair.
- valgebra and vtjson reach the same decision here only for the constructs the
  compatibility layer supports; the differences ledger
  (`03-conformance.md`) records where valgebra deliberately decides
  differently.
- The comparison is the validation step only. It is not a claim that the two are
  interchangeable for every workflow.
