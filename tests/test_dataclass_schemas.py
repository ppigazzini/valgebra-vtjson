"""A dataclass written as a schema is the instance check vtjson reads.

vtjson reads a dataclass as it reads any class that is not a `TypedDict`, a
`Protocol` or a `NamedTuple`: `isinstance`, and nothing about the fields. An
instance whose field holds a value of another type, or holds nothing because it
was never set, is an instance. valgebra reads a dataclass as the class met with
a record of its fields, so the layer does not hand it over.

The axis is what an instance holds -- a field of its declared type, of another
type, unset -- crossed with the kind of dataclass and the positions a class can
sit in. The enum kinds are the other classes valgebra reads by a rule of its
own, an instance check against the enumeration, and they agree: a composite
`Flag` is an instance and not a member, and both libraries admit it.
"""

from __future__ import annotations

import dataclasses
import enum
import types
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


@dataclasses.dataclass(frozen=True)
class _Box:
    a: int


class _SubBox(_Box):
    pass


@dataclasses.dataclass(frozen=True, slots=True)
class _Slotted:
    a: int


# Hashed by identity and shown without `b`, since both would read the field that
# was never set.
@dataclasses.dataclass(eq=False)
class _Late:
    a: int
    b: int = dataclasses.field(init=False, repr=False)


@dataclasses.dataclass(frozen=True)
class _Outer:
    inner: _Box


class _Kind(NamedTuple):
    """A dataclass, and instances of it holding what each field may hold."""

    name: str
    cls: type
    instances: Callable[[], list[object]]


KINDS = [
    _Kind("a dataclass", _Box, lambda: [_Box(1), _Box("x"), _SubBox("x")]),  # ty: ignore[invalid-argument-type]
    _Kind("a slotted one", _Slotted, lambda: [_Slotted(1), _Slotted("x")]),  # ty: ignore[invalid-argument-type]
    _Kind("one with a field never set", _Late, lambda: [_Late(1)]),
    _Kind(
        "one holding another",
        _Outer,
        lambda: [_Outer(_Box(1)), _Outer(_Box("x")), _Outer(1)],  # ty: ignore[invalid-argument-type]
    ),
]


class _Position(NamedTuple):
    """A place a schema can put a class, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any, object], object]
    lift: Callable[[object], object]


POSITIONS = [
    _Position("on its own", lambda _m, c: c, lambda v: v),
    _Position("a record's field", lambda _m, c: {"k": c}, lambda v: {"k": v}),
    _Position("a lax record's field", lambda m, c: m.lax({"k": c}), lambda v: {"k": v}),
    _Position("a dict key", lambda _m, c: {c: int}, lambda v: {v: 1}),
    _Position("a list element", lambda _m, c: [c], lambda v: [v]),
    _Position("a tuple element", lambda _m, c: (c,), lambda v: (v,)),
    _Position("Annotated metadata", lambda _m, c: Annotated[object, c], lambda v: v),
    _Position("a union's arm", lambda m, c: m.union(c, str), lambda v: v),
    _Position(
        "an attribute schema",
        lambda m, c: m.fields({"a": c}),
        lambda v: types.SimpleNamespace(a=v),
    ),
    _Position("a generic argument", lambda _m, c: list[c], lambda v: [v]),  # ty: ignore[invalid-type-form]
]


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize("kind", KINDS, ids=[k.name for k in KINDS])
def test_a_dataclass_decides_as_vtjson_does_wherever_it_is_written(
    kind: _Kind,
    position: _Position,
) -> None:
    """An instance belongs whatever its fields hold; nothing else does."""
    reference = position.wrap(vt, kind.cls)
    layer = position.wrap(vg, kind.cls)
    divergences = [
        (probe, a, b)
        for value in [*kind.instances(), 1, None, kind.cls]
        if (a := _decide(vt, reference, probe := position.lift(value)))
        != (b := _decide(vg, layer, probe))
    ]
    assert not divergences, f"{kind.name} as {position.name}: " + ", ".join(
        f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences
    )


class _Colour(enum.Flag):
    RED = 1
    GREEN = 2


class _Number(enum.IntEnum):
    ONE = 1


@pytest.mark.parametrize(
    ("schema", "values"),
    [
        (_Colour, [_Colour.RED, _Colour.RED | _Colour.GREEN, _Colour(0), 1]),
        (_Number, [_Number.ONE, 1, True, "1"]),
    ],
    ids=["Flag", "IntEnum"],
)
def test_an_enum_kind_decides_as_vtjson_does(
    schema: type,
    values: list[object],
) -> None:
    """An instance check against the enumeration, composite members included."""
    assert [_decide(vg, schema, v) for v in values] == [
        _decide(vt, schema, v) for v in values
    ]
