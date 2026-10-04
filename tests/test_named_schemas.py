"""A name that stands for another schema: a `NewType` and a type alias.

vtjson reads a `NewType` -- anything carrying `__name__` and `__supertype__` --
as the schema its supertype is, and a `typing.TypeAliasType` as the schema its
value is, each read by vtjson's own rules. So the name means whatever the
schema it names means to vtjson: a `float` that admits an `int`, a dict whose
`"a?"` key is optional, a construct, another name.

The axis is what the name stands for, crossed with the kind of name and the
positions a schema can sit in. A `typing_extensions.TypeAliasType` is a class
of its own on every supported interpreter, which vtjson does not recognise as
an alias; it is a callable vtjson refuses, and `test_callable_forms.py` holds
it.
"""

from __future__ import annotations

import sys
import typing
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, NewType, TypedDict

import pytest
import typing_extensions
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


_Inner = NewType("_Inner", float)


class _Target(NamedTuple):
    """A schema a name can stand for, built per library, and values to probe."""

    name: str
    build: Callable[[Any], object]
    values: list[object]


TARGETS = [
    _Target("float", lambda _m: float, [1, 1.5, "x", True]),
    _Target("an optional key", lambda _m: {"a?": int}, [{}, {"a": 1}, {"a": "x"}]),
    _Target("a construct", lambda m: m.ge(0), [1, -1, "x"]),
    _Target("a homogeneous list", lambda _m: [int, ...], [[], [1], ["x"]]),
    _Target("a union", lambda _m: int | None, [1, None, "x"]),
    _Target("a TypedDict", lambda _m: _Row, [{"a": 1}, {"a": "x"}, {}, {"b": 1}]),
    _Target("another NewType", lambda _m: _Inner, [1, 1.5, "x"]),
]

_NAMERS: list[tuple[str, Callable[[str, object], object]]] = [
    ("NewType", NewType),
    ("typing_extensions NewType", typing_extensions.NewType),
]
if sys.version_info >= (3, 12):
    _NAMERS.append(("TypeAliasType", typing.TypeAliasType))


class _Position(NamedTuple):
    """A place a schema can put a name, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any, object], object]
    lift: Callable[[object], object]


POSITIONS = [
    _Position("on its own", lambda _m, c: c, lambda v: v),
    _Position("a record's field", lambda _m, c: {"k": c}, lambda v: {"k": v}),
    _Position("a lax record's field", lambda m, c: m.lax({"k": c}), lambda v: {"k": v}),
    _Position("a list element", lambda _m, c: [c], lambda v: [v]),
    _Position("Annotated metadata", lambda _m, c: Annotated[object, c], lambda v: v),
    _Position("a union's arm", lambda m, c: m.union(c, bytes), lambda v: v),
    _Position("a dict key", lambda _m, c: {c: int}, lambda v: {v: 1}),
]


def _hashable(value: object) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize("target", TARGETS, ids=[t.name for t in TARGETS])
@pytest.mark.parametrize(("kind", "namer"), _NAMERS, ids=[n[0] for n in _NAMERS])
def test_a_name_decides_as_the_schema_it_names_does_in_vtjson(
    kind: str,
    namer: Callable[[str, object], object],
    target: _Target,
    position: _Position,
) -> None:
    """Every value reaches the same verdict under both libraries."""
    reference = position.wrap(vt, namer("_Named", target.build(vt)))
    layer = position.wrap(vg, namer("_Named", target.build(vg)))
    values = [v for v in target.values if _hashable(v) or position.name != "a dict key"]
    divergences = [
        (probe, a, b)
        for value in values
        if (a := _decide(vt, reference, probe := position.lift(value)))
        != (b := _decide(vg, layer, probe))
    ]
    assert not divergences, f"{kind} of {target.name} as {position.name}: " + (
        ", ".join(f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences)
    )


def _aliases() -> list[Any]:
    """Return the aliases only a `type` statement spells: a recursive one."""
    if sys.version_info < (3, 12):
        return []
    namespace: dict[str, Any] = {}
    exec("type Tree = list[Tree] | int", namespace)  # noqa: S102
    exec("type Pair[T] = list[T]", namespace)  # noqa: S102
    return [
        pytest.param(namespace["Tree"], [1, [1, [2]], ["x"], [[["x"]]]], id="Tree"),
        pytest.param(namespace["Pair"][int], [[1], ["x"], 1], id="Pair[int]"),
    ]


@pytest.mark.skipif(sys.version_info < (3, 12), reason="the `type` statement is 3.12")
@pytest.mark.parametrize(("alias", "values"), _aliases())
def test_an_alias_a_type_statement_spells_decides_as_vtjson_does(
    alias: object,
    values: list[object],
) -> None:
    """A recursive alias is a recursive schema; a subscripted one is a call."""
    divergences = [
        (value, a, b)
        for value in values
        if (a := _decide(vt, alias, value)) != (b := _decide(vg, alias, value))
    ]
    assert not divergences, ", ".join(
        f"{value!r} vtjson={a} layer={b}" for value, a, b in divergences
    )
