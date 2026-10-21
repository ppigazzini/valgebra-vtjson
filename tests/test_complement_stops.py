"""A negation decides by what the walk decided, not by where it stopped.

vtjson reads a value to the end: a callable that raises is a failure, and a
value nested past any bound is read to its last level. valgebra's walk can stop
first -- at a callable that raised, or at the bound on how deep it reads a
value -- and a stop is neither answer, so a negation cannot read it as the value
being outside. Where another part of the value decides, the stop must not:
a sequence or a record with one part that refutes is outside the schema
whatever a part beside it stopped on, and its negation admits it.

The axis is the order of the parts, crossed with the container that holds them,
the kind of stop, and each combinator that negates: `complement`, and the
`ifthen` and `cond` built from one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable

# Past the depth valgebra's walk reads a value to, and well inside the depth
# vtjson's recursion reaches on every interpreter.
DEEP = 150


def _decide(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


def _raises(obj: object) -> bool:
    msg = f"no answer for {obj!r}"
    raise ValueError(msg)


def _chain() -> dict[object, object]:
    """Return a record whose optional field is the record itself."""
    node: dict[object, object] = {}
    node["n?"] = node
    return node


def _nested(depth: int) -> dict[str, object]:
    """Return a member of `_chain` nested ``depth`` levels deep."""
    value: dict[str, object] = {}
    for _ in range(depth):
        value = {"n": value}
    return value


# Each kind of stop: the schema part, and a value that part stops on.
STOPS: list[tuple[str, Callable[[], object], Callable[[], object]]] = [
    ("a callable that raises", lambda: _raises, lambda: "s"),
    ("a member past the walk's bound", _chain, lambda: _nested(DEEP)),
]


def _parts(kind: str, stop: object, other: object, *, stop_first: bool) -> object:
    """Hold ``stop`` and ``other`` in a container of ``kind``, in the order given."""
    if kind == "record":
        pairs = [("a", stop), ("b", other)]
        return dict(pairs if stop_first else pairs[::-1])
    items = [stop, other] if stop_first else [other, stop]
    return items if kind == "list" else tuple(items)


# Each combinator that negates, and how it is spelled in a library ``m``.
NEGATIONS: list[tuple[str, Callable[[Any, object], object]]] = [
    ("complement", lambda m, s: m.complement(s)),
    ("ifthen", lambda m, s: m.ifthen(s, m.complement(m.anything))),
    (
        "cond",
        lambda m, s: m.cond((s, m.complement(m.anything)), (m.anything, m.anything)),
    ),
]

CONTAINERS = ["list", "tuple", "record"]


@pytest.mark.parametrize("stop_first", [True, False], ids=["stop first", "stop last"])
@pytest.mark.parametrize("container", CONTAINERS)
@pytest.mark.parametrize(
    ("stop", "schema", "value"), STOPS, ids=[row[0] for row in STOPS]
)
def test_a_part_that_refutes_decides_beside_a_stop(
    stop: str,
    schema: Callable[[], object],
    value: Callable[[], object],
    container: str,
    *,
    stop_first: bool,
) -> None:
    """The negation admits the value, whichever part the walk met first."""

    def build(module: Any) -> list[tuple[str, object]]:
        inner = _parts(container, schema(), int, stop_first=stop_first)
        return [(name, negate(module, inner)) for name, negate in NEGATIONS]

    obj = _parts(container, value(), "x", stop_first=stop_first)
    divergences = [
        (name, a, b)
        for (name, reference), (_, layer) in zip(build(vt), build(vg), strict=True)
        if (a := _decide(vt, reference, obj)) != (b := _decide(vg, layer, obj))
    ]
    assert not divergences, f"{stop} in a {container}: " + ", ".join(
        f"{name} vtjson={a} layer={b}" for name, a, b in divergences
    )


def _scalars_at_the_bound(m: Any) -> dict[object, object]:
    """Return a record whose scalar union reaches the walk's bound in a member."""
    node: dict[object, object] = {"b": m.union(int, str)}
    node["a?"] = {"x": {"y": node}}
    return node


def _deep_record(depth: int, leaf: object) -> dict[str, object]:
    """Return a value of `_scalars_at_the_bound`'s shape, ``depth`` levels deep."""
    value: dict[str, object] = {"b": leaf}
    for _ in range(depth):
        value = {"a": {"x": {"y": value}}, "b": leaf}
    return value


@pytest.mark.parametrize(
    ("label", "negate"), NEGATIONS, ids=[row[0] for row in NEGATIONS]
)
def test_a_member_past_the_bound_is_not_in_the_negation(
    label: str, negate: Callable[[Any, object], object]
) -> None:
    """A scalar the walk never read is not read as one the schema refuses."""
    probes = [
        _deep_record(depth, leaf)
        for depth in (10, DEEP // 3, DEEP)
        for leaf in (1, 1.5)
    ]
    reference = negate(vt, _scalars_at_the_bound(vt))
    layer = negate(vg, _scalars_at_the_bound(vg))
    divergences = [
        (index, a, b)
        for index, obj in enumerate(probes)
        if (a := _decide(vt, reference, obj)) != (b := _decide(vg, layer, obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"probe {index} vtjson={a} layer={b}" for index, a, b in divergences
    )
