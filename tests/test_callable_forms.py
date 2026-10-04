"""Every shape a callable predicate can take.

vtjson reads a bare callable as a predicate over any value, so the kind of
callable is a surface in its own right: a function and a lambda are the obvious
ones, but a bound method, an object with `__call__`, a builtin and a
`functools.partial` all reach the same path and are all things a schema is
written with.

A `partial` is the one that separates the implementations. It carries its
wrapped callable on `.func`, which is also how `annotated_types.Predicate`
carries its own, so a reader that takes `.func` from whichever marker has one
strips the partial of the arguments bound to it.

The second axis is the callable's signature. vtjson binds one argument to it
when the schema is compiled and refuses the schema with `SchemaError` where
that fails: a callable needing two arguments, or none, or one only by keyword.
A `typing_extensions.TypeAliasType` is one, a class of its own that is not
`typing`'s and whose instances take no argument.
"""

from __future__ import annotations

import functools
import operator
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

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


def _is_positive(value: object) -> bool:
    """Whether ``value`` is a positive number."""
    return isinstance(value, int) and value > 0


class _Callable:
    """A predicate carried by an instance rather than by a function."""

    def __call__(self, value: object) -> bool:
        return value == "yes"


class _Holder:
    """A class whose bound method is the predicate."""

    def positive(self, value: object) -> bool:
        return _is_positive(value)

    @staticmethod
    def negative(value: object) -> bool:
        return isinstance(value, int) and value < 0


def _generator(value: object) -> Any:
    """Yield ``value``; calling this returns a generator, which is truthy."""
    yield value


ROWS: list[tuple[str, Callable[..., Any]]] = [
    ("a function", _is_positive),
    ("a lambda", lambda value: value == 1),
    ("an object with __call__", _Callable()),
    ("a bound method", _Holder().positive),
    ("a staticmethod", _Holder.negative),
    ("a partial", functools.partial(operator.eq, 1)),
    ("a partial over contains", functools.partial(operator.contains, [1, 2])),
    ("a builtin", len),
    ("an unbound method", str.isdigit),
    ("a generator function", _generator),
    ("operator.truth", operator.truth),
]

VALUES: list[object] = [1, 2, -1, 0, "yes", "", "12", [1], [], None]


@pytest.mark.parametrize(("label", "predicate"), ROWS, ids=[r[0] for r in ROWS])
def test_a_callable_predicate_decides_as_vtjson_does(
    label: str,
    predicate: Callable[..., Any],
) -> None:
    """Every value reaches the same verdict under both libraries."""
    divergences = [
        (obj, a, b)
        for obj in VALUES
        if (a := _decide(vt, predicate, obj)) != (b := _decide(vg, predicate, obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


def _two(value: object, other: object) -> bool:
    return value == other


def _none() -> bool:
    return True


def _keyword_only(*, value: object) -> bool:
    return value == 1


def _then_keyword(value: object, *, other: object) -> bool:
    return value == other


def _defaulted(value: object, other: object = 1) -> bool:
    return value == other


def _variadic(*values: object) -> bool:
    return values == (1,)


def _keywords(**values: object) -> bool:
    return bool(values)


_Alias = typing_extensions.TypeAliasType("_Alias", int)


class _CalledBare:
    """An object whose `__call__` takes no argument."""

    def __call__(self) -> bool:
        return True


# Each signature, and whether vtjson can call it with one argument.
SIGNATURES: list[tuple[str, object]] = [
    ("two required", _two),
    ("none", _none),
    ("keyword-only", _keyword_only),
    ("a required keyword after it", _then_keyword),
    ("a default after it", _defaulted),
    ("variadic positional", _variadic),
    ("variadic keyword", _keywords),
    ("__call__ taking none", _CalledBare()),
    ("a partial binding every argument", functools.partial(_two, 1, 1)),
    ("a partial leaving one", functools.partial(_two, 1)),
    ("a lambda of two", lambda value, other: value == other),
    ("a typing_extensions alias", _Alias),
]


class _Position(NamedTuple):
    """A place a schema can put a callable, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any, object], object]
    lift: Callable[[object], object]


POSITIONS = [
    _Position("on its own", lambda _m, c: c, lambda v: v),
    _Position("a record's field", lambda _m, c: {"k": c}, lambda v: {"k": v}),
    _Position("a list element", lambda _m, c: [c], lambda v: [v]),
    _Position("a dict key", lambda _m, c: {c: int}, lambda v: {v: 1}),
    _Position("Annotated metadata", lambda _m, c: Annotated[object, c], lambda v: v),
    _Position("a union's arm", lambda m, c: m.union(c, bytes), lambda v: v),
    _Position("a lax record's field", lambda m, c: m.lax({"k": c}), lambda v: {"k": v}),
]


def _outcome(module: Any, build: Callable[[], object], obj: object) -> str:
    """Return ``module``'s verdict, or that it refused the schema it was given.

    The schema is built inside, since a wrapper may refuse it when it is written
    rather than when a value arrives.
    """
    try:
        module.validate(build(), obj)
    except module.SchemaError:
        return "SchemaError"
    except module.ValidationError:
        return "reject"
    return "accept"


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize(
    ("label", "predicate"), SIGNATURES, ids=[s[0] for s in SIGNATURES]
)
def test_a_callable_is_refused_where_vtjson_cannot_call_it_with_one_argument(
    label: str,
    predicate: object,
    position: _Position,
) -> None:
    """The schema is refused, or decides, as vtjson's does."""
    divergences = [
        (probe, a, b)
        for value in (1, 2, "x", None)
        if (
            a := _outcome(
                vt, lambda: position.wrap(vt, predicate), probe := position.lift(value)
            )
        )
        != (b := _outcome(vg, lambda: position.wrap(vg, predicate), probe))
    ]
    assert not divergences, f"{label} as {position.name}: " + ", ".join(
        f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences
    )
