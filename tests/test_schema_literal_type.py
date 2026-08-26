"""The class a schema literal is written in is part of what it demands.

vtjson dispatches a container schema on the abstract kind — mapping, sequence,
set — and then requires the value to be an instance of the literal's own class.
An `OrderedDict` schema therefore admits no plain `dict`, and a named tuple
schema admits no plain tuple. Reading only the structure loses that.

A `frozenset` schema is the odd one out and is included deliberately: vtjson
requires both `frozenset` and `set`, which nothing satisfies, so the schema is
uninhabited. Matching it is what a 1:1 layer owes; diverging in the direction of
"more useful" is how a compatibility layer stops being one.
"""

from __future__ import annotations

from collections import (
    Counter,
    OrderedDict,
    UserDict,
    UserList,
    defaultdict,
    deque,
    namedtuple,
)
from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable

Point = namedtuple("Point", "x y")  # noqa: PYI024


def _decide(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


def _dispatch_defaultdict() -> defaultdict:
    """Return a defaultdict written as a schema."""
    return defaultdict(None, {"a": int})


# A label, a builder run once per library, and the objects to probe.
ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    # A subclass literal narrows the contract to that subclass.
    (
        "OrderedDict schema",
        lambda m: OrderedDict({"a": int}),  # noqa: ARG005
        [{"a": 1}, OrderedDict(a=1), OrderedDict(a="x")],
    ),
    (
        "defaultdict schema",
        lambda m: _dispatch_defaultdict(),  # noqa: ARG005
        [{"a": 1}, defaultdict(None, {"a": 1})],
    ),
    (
        "namedtuple schema",
        lambda m: Point(int, str),  # noqa: ARG005
        [(1, "a"), Point(1, "a"), [1, "a"], Point(1, 2)],
    ),
    # A frozenset schema is uninhabited in vtjson, including for a value equal
    # to the literal.
    (
        "frozenset schema",
        lambda m: frozenset({int, str}),  # noqa: ARG005
        [frozenset({int, str}), frozenset({1}), {1}, {int, str}],
    ),
    # The plain builtins keep admitting every value they admitted.
    ("dict schema", lambda m: {"a": int}, [{"a": 1}, OrderedDict(a=1), {"a": "x"}]),  # noqa: ARG005
    ("list schema", lambda m: [int, int], [[1, 2], (1, 2), [1, "x"]]),  # noqa: ARG005
    ("tuple schema", lambda m: (int, str), [(1, "a"), Point(1, "a"), [1, "a"]]),  # noqa: ARG005
    ("set schema", lambda m: {int}, [{1}, frozenset({1}), {"x"}]),  # noqa: ARG005
]


@pytest.mark.parametrize(("label", "build", "objects"), ROWS, ids=[r[0] for r in ROWS])
def test_the_schema_literal_s_class_is_part_of_the_contract(
    label: str,
    build: Callable[[Any], object],
    objects: list[object],
) -> None:
    """Every probe reaches the same verdict under both libraries."""
    reference, layer = build(vt), build(vg)
    divergences = [
        (obj, _decide(vt, reference, obj), _decide(vg, layer, obj))
        for obj in objects
        if _decide(vt, reference, obj) != _decide(vg, layer, obj)
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


# A container class that is not a builtin is still a container schema: vtjson
# dispatches it on the abstract kind and demands the value be that class.
FOREIGN: list[tuple[str, Any, list[object]]] = [
    (
        "UserDict schema",
        UserDict({"a": int}),
        [UserDict(a=1), UserDict(a="x"), {"a": 1}, OrderedDict(a=1)],
    ),
    ("Counter schema", Counter({"a": int}), [Counter(a=1), {"a": 1}]),
    ("UserList schema", UserList([int]), [UserList([1]), UserList(["x"]), [1]]),
    ("deque schema", deque([int]), [deque([1]), deque(["x"]), [1]]),
]


@pytest.mark.parametrize(
    ("label", "schema", "objects"), FOREIGN, ids=[f[0] for f in FOREIGN]
)
def test_a_container_class_outside_the_builtins_is_still_a_container(
    label: str,
    schema: Any,
    objects: list[object],
) -> None:
    """Read for its shape, and demanded of the value by its class."""
    divergences = [
        (obj, _decide(vt, schema, obj), _decide(vg, schema, obj))
        for obj in objects
        if _decide(vt, schema, obj) != _decide(vg, schema, obj)
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
