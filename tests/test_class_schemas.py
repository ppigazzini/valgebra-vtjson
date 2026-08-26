"""A class used as a schema is read by what kind of class it is.

vtjson decides three kinds **structurally** — by the type hints the class
declares, against the value's own attributes or items — and everything else
nominally, by an instance check. A `TypedDict` describes a mapping's items; a
`Protocol` and a `NamedTuple` describe an object's attributes, and the
`NamedTuple` demands a tuple beside them.

Structural means the value's class is not consulted. Two `NamedTuple`s declaring
the same field are the same schema, and a wider one satisfies a narrower one, so
a `NamedTuple` schema is nothing like the instance check it resembles.

A class declaring no hints at all constrains nothing, which makes it a schema
that admits every value. That is vtjson's, and reproducing it is what a
one-to-one layer owes; the alternative is a layer that cannot be used to find
out which of the two libraries is wrong.
"""

from __future__ import annotations

import collections
import dataclasses
import enum
from typing import (
    TYPE_CHECKING,
    Any,
    NamedTuple,
    Protocol,
    TypedDict,
    runtime_checkable,
)

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


class _Pt(NamedTuple):
    a: int


class _PtSame(NamedTuple):
    a: int


class _PtWide(NamedTuple):
    a: int
    b: str


class _PtStr(NamedTuple):
    a: str


_Bare = collections.namedtuple("_Bare", "a")  # noqa: PYI024
_Big = collections.namedtuple("_Big", "a b c")  # noqa: PYI024


class _Row(TypedDict):
    a: int


@runtime_checkable
class _HasA(Protocol):
    a: int


class _HasAPlain(Protocol):
    a: int


@dataclasses.dataclass
class _Box:
    a: int


class _NoHints:
    """A class carrying annotations of its own is what the gate asks for."""


class _Colour(enum.Enum):
    RED = "red"


# One value per way a class schema can be satisfied or missed: the same class, a
# different class declaring the same field, a wider one, one whose field has the
# wrong type, a tuple with no attributes at all, and values of other kinds.
VALUES: list[object] = [
    _Pt(1),
    _PtSame(1),
    _PtWide(1, "x"),
    _PtStr("x"),
    _Bare(1),
    _Bare("x"),
    _Big(1, 2, 3),
    (1,),
    (),
    [1],
    {"a": 1},
    _Box(1),
    1,
    None,
    _Colour.RED,
]

ROWS: list[tuple[str, object]] = [
    # Structural: the hints are checked against the value's attributes, and a
    # tuple is demanded beside them.
    ("NamedTuple", _Pt),
    ("wider NamedTuple", _PtWide),
    # A bare `namedtuple` declares no hints, so the structural half constrains
    # nothing and every tuple belongs.
    ("bare namedtuple", _Bare),
    # Structural: the hints against the attributes, with no tuple demanded and
    # no instance check — `runtime_checkable` is not what decides.
    ("runtime Protocol", _HasA),
    ("plain Protocol", _HasAPlain),
    # Structural: the hints against a mapping's items.
    ("TypedDict", _Row),
    # Nominal: an instance check, which is what a plain class means.
    ("dataclass", _Box),
    ("class with no hints", _NoHints),
    ("Enum", _Colour),
]


@pytest.mark.parametrize(("label", "schema"), ROWS, ids=[r[0] for r in ROWS])
def test_a_class_schema_decides_as_vtjson_does(label: str, schema: object) -> None:
    """Every value reaches the same verdict under both libraries."""
    divergences = [
        (obj, a, b)
        for obj in VALUES
        if (a := _decide(vt, schema, obj)) != (b := _decide(vg, schema, obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


# `protocol` refuses a schema it cannot read hints from at all. Carrying an
# empty `__annotations__` is not that: it is a class that constrains nothing.
GATE: list[tuple[str, object]] = [
    ("object", object),
    ("int", int),
    ("a class with no annotations of its own", _NoHints),
    ("a bare namedtuple", _Bare),
    ("a TypedDict", _Row),
]


@pytest.mark.parametrize(("label", "cls"), GATE, ids=[g[0] for g in GATE])
def test_protocol_refuses_the_same_schemas_vtjson_refuses(
    label: str, cls: object
) -> None:
    """Whether the schema builds, and what it decides if it does."""

    def outcome(module: Any, construct: Callable[[object], object]) -> str:
        try:
            schema = construct(cls)
        except module.SchemaError:
            return "SchemaError"
        return f"builds/{_decide(module, schema, 12345)}"

    assert outcome(vg, vg.protocol) == outcome(vt, vt.protocol), label
