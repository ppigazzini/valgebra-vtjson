"""Every construct, in every position a schema can put one.

`test_differential.py` crosses constructs with objects and
`test_argument_space.py` crosses their arguments. Both hold the construct in the
same place: written on its own, or as a record's field. A construct is also a
dict *key*, a list element, a set member, `Annotated` metadata, and an argument
to a subscripted generic — and the translator classifies each of those
positions separately.

That is the axis this module runs. A rule applied in one position and not in its
neighbour is the defect this layer keeps having, and position is where a
construct stops being recognised as a schema at all: read as a constant, a
construct written as a dict key declares a key the mapping must carry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

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


class _Construct(NamedTuple):
    """A construct, with a value it admits and one it does not.

    Both values are hashable, so every construct can also be probed where a
    schema needs a hashable — a set member, a dict key.
    """

    name: str
    build: Callable[[Any], Any]
    admitted: object
    refused: object


class _Position(NamedTuple):
    """A place a schema can put a construct, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any], object]
    lift: Callable[[object], object]


CONSTRUCTS = [
    _Construct("ge", lambda m: m.ge(0), 1, -1),
    _Construct("interval", lambda m: m.interval(0, 10), 5, 99),
    _Construct("regex", lambda m: m.regex("[a-z]+"), "ab", "AB"),
    _Construct("union", lambda m: m.union(int, str), 1, None),
    _Construct("intersect", lambda m: m.intersect(int, m.ge(0)), 1, -1),
    _Construct("ifthen", lambda m: m.ifthen(int, m.ge(0)), 1, -1),
    _Construct("complement", lambda m: m.complement(str), 1, "x"),
    _Construct("quote", lambda m: m.quote(str), str, "x"),
    _Construct("div", lambda m: m.div(2), 4, 5),
    _Construct("close_to", lambda m: m.close_to(1.0), 1.0, 9.0),
    _Construct("set_name", lambda m: m.set_name(int, "n"), 1, "x"),
]

POSITIONS = [
    _Position("on its own", lambda c: c, lambda v: v),
    _Position("a record's field", lambda c: {"k": c}, lambda v: {"k": v}),
    _Position("a dict key", lambda c: {c: int}, lambda v: {v: 1}),
    _Position("a list element", lambda c: [c], lambda v: [v]),
    _Position("a repeated element", lambda c: [c, ...], lambda v: [v, v]),
    _Position("a tuple element", lambda c: (c,), lambda v: (v,)),
    _Position("a set member", lambda c: {c}, lambda v: {v}),
    _Position("Annotated metadata", lambda c: Annotated[object, c], lambda v: v),
    _Position("nested two deep", lambda c: {"x": {"y": c}}, lambda v: {"x": {"y": v}}),
    _Position("a generic argument", lambda c: list[c], lambda v: [v]),
]


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize("construct", CONSTRUCTS, ids=[c.name for c in CONSTRUCTS])
def test_a_construct_decides_the_same_wherever_it_is_written(
    position: _Position,
    construct: _Construct,
) -> None:
    """The verdict follows the construct, not where the schema puts it."""
    reference = position.wrap(construct.build(vt))
    layer = position.wrap(construct.build(vg))
    divergences = [
        (probe, a, b)
        for value in (construct.admitted, construct.refused)
        if (probe := position.lift(value)) is not None
        and (a := _decide(vt, reference, probe)) != (b := _decide(vg, layer, probe))
    ]
    assert not divergences, f"{construct.name} as {position.name}: " + ", ".join(
        f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences
    )
