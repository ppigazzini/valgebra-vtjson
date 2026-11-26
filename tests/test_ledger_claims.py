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

import re
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


def test_a_refusal_reports_one_failure_as_vtjson_does() -> None:
    """The error report row: a value wrong in four places is refused by one.

    vtjson's report is the first failure its walk meets. The layer's is the
    first of valgebra's report, so a call that refuses pays for that one, and a
    caller reading `err.errors` reads one violation however many the value has.
    """
    schema = {"a": int, "b": int, "c": [str, ...]}
    value = {"a": "x", "b": "y", "c": [1, 2]}
    with pytest.raises(vt.ValidationError):
        vt.validate(schema, value)
    with pytest.raises(vg.ValidationError) as validated:
        vg.validate(schema, value)
    with pytest.raises(vg.ValidationError) as cast:
        vg.safe_cast(schema, value)
    assert len(validated.value.errors) == len(cast.value.errors) == 1
    assert validated.value.path == cast.value.path == ("a",)
    explanation = vg.compile(schema).__validate__(value, "object", True, {})
    assert explanation == str(validated.value)
    row = next(line for line in _LEDGER.splitlines() if "| Error report |" in line)
    assert "one structured violation" in row


@pytest.mark.parametrize(
    ("schema", "value", "place", "path"),
    [
        (int, "x", "request", ()),
        ({"worker_info": {"worker_arch": str}}, {"worker_info": {"worker_arch": 1}},
         "request['worker_info']['worker_arch']", ("worker_info", "worker_arch")),
        ([int, ...], [1, "x"], "request[1]", (1,)),
        ({str: int}, {"k": "x"}, "request['k']", ("k",)),
    ],
    ids=["at the root", "under a record", "under a list", "under a mapping"],
)  # fmt: skip
def test_a_refusal_names_its_place_as_vtjson_does(
    schema: object, value: object, place: str, path: tuple[object, ...]
) -> None:
    """The error report row: the message opens with the name and vtjson's path.

    vtjson names the place a value failed as the name it was given and each key
    and index after it; the layer's message opens with the same place, before
    valgebra's expectation, and the failure's code and path stay valgebra's.
    """
    with pytest.raises(vt.ValidationError) as told:
        vt.validate(schema, value, "request")
    assert str(told.value).startswith(place)
    with pytest.raises(vg.ValidationError) as refused:
        vg.validate(schema, value, "request")
    assert str(refused.value).startswith(f"{place}: expected ")
    assert (
        refused.value.message
        == str(refused.value)
        == refused.value.errors[0]["message"]
    )
    assert refused.value.path == path
    explanation = vg.compile(schema).__validate__(value, "request", True, {})
    assert explanation == str(refused.value)
    with pytest.raises(vg.ValidationError) as cast:
        vg.safe_cast(schema, value)
    assert str(cast.value).startswith(f"object{place.removeprefix('request')}: ")


def _total_games_must_match(run: object) -> bool:
    """Refuse every run: a rule written as fishtest writes its own."""
    del run
    return False


@pytest.mark.parametrize(
    ("make", "value"),
    [
        (lambda _: _total_games_must_match, {"games": 2}),
        (lambda _: lambda _obj: False, 1),
        (lambda m: m.email, "nope"),
        (lambda m: m.regex(r"^a+$"), "b"),
        (lambda m: m.regex(r"^a+$", name="letters"), "b"),
        (lambda m: m.regex(regex="a", fullmatch=False), "b"),
        (lambda m: m.div(3, 1), 3),
        (lambda m: m.div(2, name="even"), 3),
        (lambda m: m.glob("*.py"), "a.txt"),
        (lambda m: m.ip_address(version=4), "::1"),
        (lambda m: m.date_time("%Y"), "x"),
        (lambda m: m.close_to(1.0), 2.0),
        (lambda m: m.one_of("a", "b"), {}),
        (lambda m: m.unique, [1, 1]),
        (lambda _: 1.5, 2.5),
    ],
    ids=[
        "a rule", "a lambda", "a bare construct", "a construct's call",
        "a given name", "by keyword and default", "a default passed",
        "a given name over the call", "a pattern", "a keyword", "a format",
        "a tolerance", "several keys", "a nullary construct", "a float constant",
    ],
)  # fmt: skip
def test_a_refusal_names_its_schema_as_vtjson_does(
    make: Callable[[Any], object], value: object
) -> None:
    """The error report row: a failed check is named by the name vtjson gives it.

    valgebra names a failed predicate by its callable, and the layer's checks
    take the name vtjson's message gives the schema: a caller's callable its
    own, a construct the call that made it or the name it was given. Where
    vtjson's refusal reads `is not of type 'div(3,remainder=1)'`, the layer's
    expects `a passing div(3,remainder=1)`.
    """
    with pytest.raises(vt.ValidationError) as told:
        vt.validate(make(vt), value, "run")
    named = re.search(r"is not of type '(.*?)'(?:: |$)", str(told.value))
    assert named is not None, str(told.value)
    with pytest.raises(vg.ValidationError) as refused:
        vg.validate(make(vg), value, "run")
    assert refused.value.errors[0]["expected"] == f"a passing {named.group(1)}"
