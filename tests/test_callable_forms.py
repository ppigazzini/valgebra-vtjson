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
"""

from __future__ import annotations

import functools
import operator
from typing import TYPE_CHECKING, Any

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
