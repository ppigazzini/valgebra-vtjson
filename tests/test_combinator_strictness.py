"""Laxness reaches the record a combinator carries.

vtjson threads strictness as a call-time flag, so it descends through everything
between the wrapper and the record — a `union`, an `ifthen`, a `set_name`. Only
`lax` and `strict` themselves stop it, because those are what set it, and the
innermost one wins.

A combinator is not one of those. `lax(union({"a": int}, str))` must reach the
record, and a combinator that settles its arguments the moment it is called has
already chosen a mode by the time an enclosing wrapper asks for another.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypedDict

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable


def _decide(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


class _Row(TypedDict):
    a: int


# The record every combinator below carries, and a value for each way a key can
# arise against it: declared and passing, declared and failing, undeclared.
_RECORD = {"a": int}

PROBES: list[object] = [
    {"a": 1},
    {"a": 1, "z": 2},
    {"a": "x"},
    {},
    {"z": 2},
    1,
    None,
]

NESTED_PROBES: list[object] = [
    *PROBES,
    {"x": {"a": 1, "z": 2}},
    {"x": {"a": 1}},
    [{"a": 1, "z": 2}],
    [{"a": 1}],
]

# Every combinator that carries a schema, and two that carry none — a
# combinator with nothing to descend into must not change either.
ROWS: list[tuple[str, Callable[[Any], object]]] = [
    ("union", lambda m: m.union(_RECORD, str)),
    ("intersect", lambda m: m.intersect(_RECORD, dict)),
    ("ifthen", lambda m: m.ifthen(dict, _RECORD)),
    ("ifthen with else", lambda m: m.ifthen(str, str, _RECORD)),
    ("cond", lambda m: m.cond((dict, _RECORD), (object, str))),
    ("complement", lambda m: m.complement(_RECORD)),
    ("filter", lambda m: m.filter(lambda obj: obj, _RECORD)),
    ("set_name", lambda m: m.set_name(_RECORD, "row")),
    ("set_label", lambda m: m.set_label(_RECORD, "label")),
    ("protocol as a dict", lambda m: m.protocol(_Row, dict=True)),
    ("fields", lambda m: m.fields({"a": int})),
    ("quote", lambda m: m.quote(_RECORD)),
    ("keys", lambda m: m.keys("a")),
    # A combinator inside a container, and a container inside a combinator.
    ("in a record", lambda m: {"x": m.union(_RECORD, str)}),
    ("in a list", lambda m: [m.union(_RECORD, str)]),
    ("around a record", lambda m: m.union({"x": _RECORD}, str)),
    ("nested combinators", lambda m: m.union(m.intersect(_RECORD, dict), str)),
]


@pytest.mark.parametrize("wrapper", ["bare", "lax", "strict"])
@pytest.mark.parametrize(("label", "build"), ROWS, ids=[r[0] for r in ROWS])
def test_strictness_reaches_through_a_combinator(
    label: str,
    build: Callable[[Any], object],
    wrapper: str,
) -> None:
    """Every probe reaches the same verdict under both libraries."""

    def wrapped(module: Any) -> object:
        schema = build(module)
        return schema if wrapper == "bare" else getattr(module, wrapper)(schema)

    reference, layer = wrapped(vt), wrapped(vg)
    divergences = [
        (obj, a, b)
        for obj in NESTED_PROBES
        if (a := _decide(vt, reference, obj)) != (b := _decide(vg, layer, obj))
    ]
    assert not divergences, f"{label}/{wrapper}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


# `lax` and `strict` are what set the mode, so an enclosing one cannot override
# an inner one — the rule a combinator must not be caught by.
TOWERS: list[tuple[str, Callable[[Any], object]]] = [
    ("lax(strict(union))", lambda m: m.lax(m.strict(m.union(_RECORD, str)))),
    ("strict(lax(union))", lambda m: m.strict(m.lax(m.union(_RECORD, str)))),
    ("lax(union(strict))", lambda m: m.lax(m.union(m.strict(_RECORD), str))),
    ("lax(union(lax))", lambda m: m.lax(m.union(m.lax(_RECORD), str))),
]


@pytest.mark.parametrize(("label", "build"), TOWERS, ids=[t[0] for t in TOWERS])
def test_the_innermost_wrapper_still_decides(
    label: str, build: Callable[[Any], object]
) -> None:
    """A combinator between two wrappers does not become one."""
    divergences = [
        (obj, a, b)
        for obj in PROBES
        if (a := _decide(vt, build(vt), obj)) != (b := _decide(vg, build(vg), obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
