"""The ledger's checkable claims, checked.

A differences ledger is prose a reader is asked to trust, and most of its rows
are about intent. Some are measurements — how deep a schema may nest, and what a
recommended shape costs — and a measurement in prose that nothing re-runs is a
number that was true once.

These pin the depth rows: how deep a schema may nest, and how deep a value is
read against a recursive one. Each limit belongs to valgebra rather than to this
layer, so a valgebra release can move it; that is the point of measuring here
rather than quoting.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable

_LEDGER = (
    Path(__file__).resolve().parent.parent / "docs" / "03-conformance.md"
).read_text(encoding="utf-8")

# Far past any bound, so a shape that never refuses fails rather than hangs.
_CEILING = 300


def _first_refused_depth(wrap: Callable[[Any], Any]) -> int:
    """Return the nesting depth at which the translator first refuses ``wrap``."""
    schema: Any = int
    for depth in range(1, _CEILING):
        schema = wrap(schema)
        try:
            vg.compile(schema)
        except Exception:  # noqa: BLE001  (any refusal is the bound being hit)
            return depth
    pytest.fail(f"no depth below {_CEILING} was refused")
    return _CEILING  # pragma: no cover - pytest.fail does not return


SHAPES: list[tuple[str, Callable[[Any], Any]]] = [
    ("a one-element list", lambda inner: [inner]),
    ("a homogeneous list", lambda inner: [inner, ...]),
]


@pytest.mark.parametrize(("label", "wrap"), SHAPES, ids=[s[0] for s in SHAPES])
def test_the_ledger_names_the_depth_each_shape_reaches(
    label: str, wrap: Callable[[Any], Any]
) -> None:
    """A shape the ledger recommends is one whose cost it states."""
    depth = _first_refused_depth(wrap)
    assert str(depth) in _LEDGER, (
        f"{label} is refused at {depth} levels and docs/03-conformance.md does "
        f"not say so; a reader choosing between shapes needs both numbers"
    )


def test_the_recommended_shape_is_the_deeper_one() -> None:
    """The migration note is only advice if the shape it names goes deeper."""
    assert _first_refused_depth(lambda inner: [inner, ...]) > _first_refused_depth(
        lambda inner: [inner]
    )


def _holding_itself(m: Any) -> object:
    """Return a record whose optional field is the record itself."""
    del m
    node: dict[object, object] = {}
    node["n?"] = node
    return node


def _records(depth: int) -> object:
    value: dict[str, object] = {}
    for _ in range(depth):
        value = {"n": value}
    return value


def _listing_itself(m: Any) -> object:
    """Return a list whose elements are an int or the list itself."""
    node: list[object] = []
    node.extend([m.union(int, node), ...])
    return node


def _lists(depth: int) -> object:
    value: object = 1
    for _ in range(depth):
        value = [value]
    return value


VALUE_SHAPES: list[tuple[str, Callable[[Any], object], Callable[[int], object]]] = [
    ("a record holding itself", _holding_itself, _records),
    ("a list of itself in a union", _listing_itself, _lists),
]


def _first_refused_value(schema: object, nest: Callable[[int], object]) -> int:
    """Return the depth at which the layer first refuses a value ``nest`` builds."""
    validator = vg.compile(schema)
    for depth in range(1, _CEILING):
        if not validator.is_valid(nest(depth)):
            return depth
    pytest.fail(f"no value nested below {_CEILING} was refused")
    return _CEILING  # pragma: no cover - pytest.fail does not return


@pytest.mark.parametrize(
    ("label", "schema", "nest"), VALUE_SHAPES, ids=[s[0] for s in VALUE_SHAPES]
)
def test_the_ledger_names_the_depth_a_value_is_read_to(
    label: str, schema: Callable[[Any], object], nest: Callable[[int], object]
) -> None:
    """The row is a decision: vtjson admits the value the layer refuses there."""
    depth = _first_refused_value(schema(vg), nest)
    row = next(
        (line for line in _LEDGER.splitlines() if "Value nesting depth" in line), ""
    )
    assert f"nested {depth} levels" in row, (
        f"{label}: a value nested {depth} levels is refused and the value depth "
        f"row of docs/03-conformance.md does not say so"
    )
    with pytest.raises(vg.ValidationError) as refused:
        vg.validate(schema(vg), nest(depth))
    assert refused.value.code == "recursion_limit"
    vt.validate(schema(vt), nest(depth))
