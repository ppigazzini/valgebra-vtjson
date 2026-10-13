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

A subscripted alias is neither kind of name. `Pair[int]` reports the alias as
its origin, which vtjson has no rule for, so vtjson calls it, and the call
raises on every value: the schema admits nothing. valgebra reads the same form
as the alias's body with the argument in place, `list[int]`. The axis there is
the kind of alias -- `typing`'s or `typing_extensions`', with one parameter or
two, defaulted, recursive -- crossed with the same positions.
"""

from __future__ import annotations

import sys
import typing
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    NamedTuple,
    NewType,
    TypedDict,
    TypeVar,
)

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
    _Position("a generic's argument", lambda _m, c: list[c], lambda v: [v]),  # ty: ignore[invalid-type-form]
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
    """Return the alias only a `type` statement spells: a recursive one."""
    if sys.version_info < (3, 12):
        return []
    namespace: dict[str, Any] = {}
    exec("type Tree = list[Tree] | int", namespace)  # noqa: S102
    return [
        pytest.param(namespace["Tree"], [1, [1, [2]], ["x"], [[["x"]]]], id="Tree"),
    ]


@pytest.mark.skipif(sys.version_info < (3, 12), reason="the `type` statement is 3.12")
@pytest.mark.parametrize(("alias", "values"), _aliases())
def test_an_alias_a_type_statement_spells_decides_as_vtjson_does(
    alias: object,
    values: list[object],
) -> None:
    """A recursive alias is a recursive schema."""
    divergences = [
        (value, a, b)
        for value in values
        if (a := _decide(vt, alias, value)) != (b := _decide(vg, alias, value))
    ]
    assert not divergences, ", ".join(
        f"{value!r} vtjson={a} layer={b}" for value, a, b in divergences
    )


_T = TypeVar("_T")
_Listed = typing_extensions.TypeAliasType("_Listed", list[_T], type_params=(_T,))


def _subscripted() -> list[Any]:
    """Return each kind of subscripted alias this interpreter can spell."""
    rows = [pytest.param(_Listed[int], id="typing_extensions alias[int]")]
    namespace: dict[str, Any] = {}
    if sys.version_info >= (3, 12):
        exec("type Pair[T] = list[T]", namespace)  # noqa: S102
        exec("type Two[K, V] = dict[K, V]", namespace)  # noqa: S102
        exec("type Nest[T] = T | list[Nest[T]]", namespace)  # noqa: S102
        rows += [
            pytest.param(namespace["Pair"][int], id="Pair[int]"),
            pytest.param(namespace["Pair"][float], id="Pair[float]"),
            pytest.param(namespace["Two"][str, int], id="Two[str, int]"),
            pytest.param(namespace["Nest"][int], id="Nest[int]"),
        ]
    if sys.version_info >= (3, 13):
        exec("type Defaulted[T = int] = list[T]", namespace)  # noqa: S102
        rows.append(pytest.param(namespace["Defaulted"][str], id="Defaulted[str]"))
    return rows


# What each alias's body admits, and values it does not, so a layer reading the
# body diverges on the first kind and a layer making vtjson's call on neither.
_BODIES: list[object] = [[], [1], [1.5], ["x"], 1, "x", {}, {"a": 1}]


def _outcome(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj``, or the class of what it raised.

    Before 3.11 `inspect.signature` cannot read a subscripted
    `typing_extensions` alias and raises `ValueError`, and vtjson asks it when
    the schema is compiled. The layer asks the same question, so agreeing is
    raising the same class there.
    """
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    except Exception as exc:  # noqa: BLE001  (the refusal is the answer being compared)
        return type(exc).__name__
    return "accept"


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize("alias", _subscripted())
def test_a_subscripted_alias_is_the_call_vtjson_makes(
    alias: object,
    position: _Position,
) -> None:
    """Every value reaches the same verdict under both libraries."""
    values = [v for v in _BODIES if _hashable(v) or position.name != "a dict key"]
    divergences = [
        (probe, a, b)
        for value in values
        if (a := _outcome(vt, position.wrap(vt, alias), probe := position.lift(value)))
        != (b := _outcome(vg, position.wrap(vg, alias), probe))
    ]
    assert not divergences, f"{alias!r} as {position.name}: " + (
        ", ".join(f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences)
    )
