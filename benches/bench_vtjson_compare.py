"""Performance comparison: vtjson against valgebra, on the same vtjson schemas.

This is the comparison that belongs here rather than in valgebra: it measures
how much faster the same vtjson-style schema validates when translated onto
valgebra's Rust core than under pinned pure-Python vtjson.

Both sides compile the schema once and time a single membership check on a
passing value:

- **vtjson** compiles with ``vtjson.compile`` and validates the compiled schema
  with ``vtjson.validate`` (its compile-once path, no recompilation per call).
- **valgebra** translates the same schema with ``vtjson_compat.compile`` and
  checks membership with ``CompiledValidator.is_valid``.

Both decide membership without coercion, so the comparison is like-for-like (in
contrast to a pydantic comparison, where pydantic also constructs output). The
shapes are the same vtjson value in both columns, since both libraries read the
implicit forms identically.

Not collected by the default test run (``testpaths = tests``); run with
``uv run --group bench pytest benches/bench_vtjson_compare.py`` after installing
the ``bench`` dependency group. The harness is pytest-benchmark.
"""

from __future__ import annotations

import pytest
import vtjson as vt

import vtjson_compat as vg

RECORD_WIDTH = 50
MAPPING_SIZE = 50
ARRAY_LEN = 10_000
NEST_DEPTH = 12

LIBRARIES = ["vtjson", "valgebra"]

# Each shape returns ``(vt_schema, vg_schema, data)``. The implicit forms (dict,
# list, scalar) read identically in both libraries, so they share one object;
# the combinator forms (union, intersect, regex) are spelled with each library's
# own constructs, since those are different callables. ``data`` is a passing
# value: the membership fast path both libraries optimize.


def shape_scalar() -> tuple[object, object, object]:
    return int, int, 42


def shape_record() -> tuple[object, object, object]:
    schema = {f"f{i}": int for i in range(RECORD_WIDTH)}
    data = {f"f{i}": i for i in range(RECORD_WIDTH)}
    return schema, schema, data


def shape_mapping() -> tuple[object, object, object]:
    schema = {str: int}
    data = {f"k{i}": i for i in range(MAPPING_SIZE)}
    return schema, schema, data


def shape_array() -> tuple[object, object, object]:
    schema = [int, ...]
    data = list(range(ARRAY_LEN))
    return schema, schema, data


def shape_nested() -> tuple[object, object, object]:
    schema = {"user": {"name": str, "age?": int}, "tags": [str, ...]}
    data = {"user": {"name": "Ada", "age": 36}, "tags": ["a", "b", "c"]}
    return schema, schema, data


def shape_deep() -> tuple[object, object, object]:
    schema: object = int
    data: object = 0
    for _ in range(NEST_DEPTH):
        schema = {"next": schema}
        data = {"next": data}
    return schema, schema, data


def shape_union() -> tuple[object, object, object]:
    # A discriminated string set plus a numeric arm; the value hits the last arm.
    return (
        vt.union("pending", "active", "finished", int),
        vg.union("pending", "active", "finished", int),
        42,
    )


def shape_refinement() -> tuple[object, object, object]:
    # A bounded integer: the intersect-of-comparisons refinement family.
    return (
        vt.intersect(int, vt.ge(0), vt.lt(1000)),
        vg.intersect(int, vg.ge(0), vg.lt(1000)),
        500,
    )


def shape_format() -> tuple[object, object, object]:
    # A regular-expression string format, the same engine on both sides.
    pattern = r"[0-9a-f]{24}"
    return vt.regex(pattern), vg.regex(pattern), "0123456789abcdef01234567"


SHAPES = {
    "scalar": shape_scalar,
    "record": shape_record,
    "mapping": shape_mapping,
    "array": shape_array,
    "nested": shape_nested,
    "deep": shape_deep,
    "union": shape_union,
    "refinement": shape_refinement,
    "format": shape_format,
}


def vtjson_check(schema: object, data: object) -> object:
    # Compile once; validate the compiled schema, vtjson's compile-once path.
    compiled = vt.compile(schema)

    def check() -> None:
        vt.validate(compiled, data)

    vt.validate(compiled, data)  # precondition: the value passes
    return check


def valgebra_check(schema: object, data: object) -> object:
    validator = vg.compile(schema)
    assert validator.is_valid(data) is True  # precondition: the value passes
    return validator.is_valid


@pytest.mark.parametrize("lib", LIBRARIES)
@pytest.mark.parametrize("shape", list(SHAPES))
def test_compare(benchmark: object, shape: str, lib: str) -> None:
    benchmark.group = shape  # type: ignore[attr-defined]
    vt_schema, vg_schema, data = SHAPES[shape]()
    if lib == "vtjson":
        benchmark(vtjson_check(vt_schema, data))
    else:
        benchmark(valgebra_check(vg_schema, data), data)
