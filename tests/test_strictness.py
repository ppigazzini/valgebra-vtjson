"""What `lax` and `strict` do to a dict that has a catch-all.

vtjson decides a key by the clauses that claim it, and strictness only settles
what happens to a key **no** clause claims: `strict` rejects it, `lax` admits it.
A typed catch-all is a clause either way, so neither mode may discard it.

Reaching that through `Validator.open`/`close` cannot work — `open` adds a clause
matching every key, which subsumes the typed one, and `close` drops the typed one
outright. Both lose the constraint the schema was written to carry.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, NamedTuple, TypedDict

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable


def _decide(module: Any, schema: object, obj: object, **kwargs: Any) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj, **kwargs)
    except module.ValidationError:
        return "reject"
    return "accept"


# A record with a typed catch-all, and a value for each way a key can arise:
# named, claimed by the catch-all and passing, claimed and failing, claimed by
# nothing at all.
MIXED: list[object] = [
    {"name": "x"},
    {"name": "x", "extra": 1},
    {"name": "x", "extra": "bad"},
    {"name": "x", 7: object()},
    {"name": 5},
]

# A plain record, where strictness is the whole question.
PLAIN: list[object] = [{"a": 1}, {"a": "x"}, {"a": 1, "b": 2}, {"b": 2}]

# An empty dict declares no clause at all, so under laxness every key is
# unclaimed and every dict belongs.
EMPTY_PROBES: list[object] = [{}, {"a": 1}, {1: "y"}, {"a": 1, "b": 2}]

ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    ("lax of an empty dict", lambda m: m.lax({}), EMPTY_PROBES),
    ("strict of an empty dict", lambda m: m.strict({}), EMPTY_PROBES),
    ("an empty dict as written", lambda m: {}, EMPTY_PROBES),  # noqa: ARG005
    ("lax of a mixed dict", lambda m: m.lax({"name": str, str: int}), MIXED),
    ("strict of a mixed dict", lambda m: m.strict({"name": str, str: int}), MIXED),
    ("a mixed dict as written", lambda m: {"name": str, str: int}, MIXED),  # noqa: ARG005
    ("lax of a plain record", lambda m: m.lax({"a": int}), PLAIN),
    ("strict of a plain record", lambda m: m.strict({"a": int}), PLAIN),
    # Strictness reaches the whole subtree, so a nested mixed dict gets it too.
    (
        "lax of a nested mixed dict",
        lambda m: m.lax({"x": {"a": int, str: int}}),
        [
            {"x": {"a": 1}},
            {"x": {"a": 1, "k": 2}},
            {"x": {"a": 1, "k": "bad"}},
            {"x": {"a": 1}, "y": 9},
        ],
    ),
]


@pytest.mark.parametrize(("label", "build", "objects"), ROWS, ids=[r[0] for r in ROWS])
def test_strictness_keeps_the_clauses_the_schema_declares(
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


@pytest.mark.parametrize("strict", [True, False], ids=["strict", "lax"])
def test_the_validate_flag_keeps_them_too(strict: bool) -> None:  # noqa: FBT001
    """`validate`'s own flag is the same question asked at the call."""
    schema = {"name": str, str: int}
    divergences = [
        (obj, a, b)
        for obj in MIXED
        if (a := _decide(vt, schema, obj, strict=strict))
        != (b := _decide(vg, schema, obj, strict=strict))
    ]
    assert not divergences, f"strict={strict}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


# A sequence declares positions the way a record declares keys, so laxness frees
# the positions after the declared ones and leaves those alone.
SEQUENCES: list[object] = [
    [],
    [1],
    [1, "a"],
    [1, "a", 99],
    [1, 2],
    ["a"],
    "not a list",
    (1, "a"),
]

SEQUENCE_ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    ("lax of a fixed list", lambda m: m.lax([int, str]), SEQUENCES),
    ("strict of a fixed list", lambda m: m.strict([int, str]), SEQUENCES),
    ("lax of a one-element list", lambda m: m.lax([int]), SEQUENCES),
    ("lax of an empty list", lambda m: m.lax([]), SEQUENCES),
    ("lax of a homogeneous list", lambda m: m.lax([int, ...]), SEQUENCES),
    (
        "lax of a fixed tuple",
        lambda m: m.lax((int, str)),
        [(), (1,), (1, "a"), (1, "a", 99), (1, 2), [1, "a"]],
    ),
    (
        "lax of an empty tuple",
        lambda m: m.lax(()),
        [(), (1,), (1, "a"), [1]],
    ),
]


@pytest.mark.parametrize(
    ("label", "build", "objects"), SEQUENCE_ROWS, ids=[r[0] for r in SEQUENCE_ROWS]
)
def test_laxness_frees_the_positions_a_sequence_does_not_declare(
    label: str,
    build: Callable[[Any], object],
    objects: list[object],
) -> None:
    """A declared position still decides; an undeclared one is free."""
    reference, layer = build(vt), build(vg)
    divergences = [
        (obj, _decide(vt, reference, obj), _decide(vg, layer, obj))
        for obj in objects
        if _decide(vt, reference, obj) != _decide(vg, layer, obj)
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


class _Point(NamedTuple):
    a: int


@dataclasses.dataclass
class _Boxed:
    a: int


class _Row(TypedDict):
    a: int


# A class can declare keys too. Laxness reaches the ones that do, and leaves the
# ones that do not — an instance check has no undeclared key to free.
CLASS_VALUES: list[object] = [{"a": 1}, {"a": "x"}, {"a": 1, "b": 2}, {}, 1]

CLASS_ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    ("lax of a TypedDict", lambda m: m.lax(_Row), CLASS_VALUES),
    ("strict of a TypedDict", lambda m: m.strict(_Row), CLASS_VALUES),
    ("a TypedDict as written", lambda m: _Row, CLASS_VALUES),  # noqa: ARG005
    ("lax of a dataclass", lambda m: m.lax(_Boxed), [_Boxed(1), {"a": 1}, 1]),
    ("lax of a NamedTuple", lambda m: m.lax(_Point), [_Point(1), (1,), (1, 2), 1]),
    ("lax of a scalar", lambda m: m.lax(int), [1, "x", None]),
]


@pytest.mark.parametrize(
    ("label", "build", "objects"), CLASS_ROWS, ids=[r[0] for r in CLASS_ROWS]
)
def test_laxness_reaches_a_class_that_declares_keys(
    label: str,
    build: Callable[[Any], object],
    objects: list[object],
) -> None:
    """A `TypedDict` declares keys, so laxness frees the ones it does not."""
    reference, layer = build(vt), build(vg)
    divergences = [
        (obj, _decide(vt, reference, obj), _decide(vg, layer, obj))
        for obj in objects
        if _decide(vt, reference, obj) != _decide(vg, layer, obj)
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


# Every tower of wrappers, against a record nested one deep with an undeclared
# key at the bottom.
TOWERS: list[tuple[str, Callable[[Any], object]]] = [
    ("none", lambda m: {"x": {"a": int}}),  # noqa: ARG005
    ("lax", lambda m: m.lax({"x": {"a": int}})),
    ("strict", lambda m: m.strict({"x": {"a": int}})),
    ("lax(strict)", lambda m: m.lax(m.strict({"x": {"a": int}}))),
    ("strict(lax)", lambda m: m.strict(m.lax({"x": {"a": int}}))),
    ("lax(lax)", lambda m: m.lax(m.lax({"x": {"a": int}}))),
    ("strict(strict)", lambda m: m.strict(m.strict({"x": {"a": int}}))),
]


@pytest.mark.parametrize(("label", "build"), TOWERS, ids=[t[0] for t in TOWERS])
@pytest.mark.parametrize(
    "mode", [{}, {"strict": True}, {"strict": False}], ids=["default", "strict", "lax"]
)
def test_the_innermost_wrapper_decides(
    label: str,
    build: Callable[[Any], object],
    mode: dict[str, Any],
) -> None:
    """A wrapper cannot reach inside one already applied, as in vtjson.

    Each wrapper builds a validator, and a validator carries the mode it was
    built with. An enclosing wrapper translates a spec, and a built validator
    translates to itself — so the innermost mode stands, which is the rule
    vtjson reaches by threading strictness as a call-time flag.
    """
    obj = {"x": {"a": 1, "extra": 2}}
    assert _decide(vg, build(vg), obj, **mode) == _decide(vt, build(vt), obj, **mode)
