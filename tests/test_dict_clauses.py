"""A key claimed by more than one clause belongs if any one of them admits it.

vtjson decides a dict key by trying every clause whose *key* applies to it — the
named field, if the key is declared, and each catch-all whose key schema matches
— and accepting as soon as one clause's value schema does. A named key that also
falls under a catch-all therefore has two ways to pass, not one.

Whether a catch-all claims a *literal* key is decidable when the schema is
built, so these rows exercise a translation-time question, not a per-value one.
"""

from __future__ import annotations

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


def _hex_key(module: Any) -> object:
    """Return a key schema claiming a 24-character hex id and nothing else."""
    return module.regex("[0-9a-f]{24}")


ID = "0" * 24

# A label, a builder run once per library, and the objects to probe.
ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    # The named key is claimed by the catch-all too, so its value may satisfy
    # either clause.
    (
        "named key under a catch-all",
        lambda m: {"name": str, str: int},  # noqa: ARG005
        [
            {"name": "x"},
            {"name": 5},
            {"name": 1.5},
            {"name": 5, "k": 1},
            {"name": "x", "k": "bad"},
        ],
    ),
    # Optionality of the named key does not change the rule.
    (
        "optional key under a catch-all",
        lambda m: {"a?": str, str: int},  # noqa: ARG005
        [{"a": "x"}, {"a": 5}, {"a": 1.5}, {}],
    ),
    # No overlap: the pattern does not claim the literal key, so there is no
    # second chance and the named clause decides alone.
    (
        "named key outside the catch-all",
        lambda m: {"last_run": str, _hex_key(m): int},
        [
            {"last_run": "x"},
            {"last_run": 5},
            {"last_run": "x", ID: 1},
            {"last_run": "x", ID: "bad"},
        ],
    ),
    # Two catch-alls claim the same key; either may admit the value.
    (
        "two overlapping catch-alls",
        lambda m: {str: int, m.regex("a.*"): str},
        [{"abc": 1}, {"abc": "hello"}, {"abc": 1.5}, {"zzz": "hello"}, {"zzz": 1}],
    ),
    # A named key claimed by two catch-alls has three clauses to satisfy.
    (
        "named key under two catch-alls",
        lambda m: {"abc": bytes, str: int, m.regex("a.*"): str},
        [{"abc": b"x"}, {"abc": 1}, {"abc": "hello"}, {"abc": 1.5}],
    ),
    # The fishtest shape: a named key that the id pattern does not claim.
    (
        "record plus id catch-all",
        lambda m: {_hex_key(m): bool, "last_run": _hex_key(m)},
        [{ID: True, "last_run": ID}, {ID: True}, {"last_run": ID}, {ID: 5}],
    ),
]


@pytest.mark.parametrize(("label", "build", "objects"), ROWS, ids=[r[0] for r in ROWS])
def test_a_key_belongs_if_any_applicable_clause_admits_it(
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


# A non-string key is a clause when it is a *schema* and a declared key when it
# is a *constant*. vtjson splits them that way, and only the second is required
# to be present.
KEY_KINDS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    ("float key", lambda m: {1.5: str}, [{}, {1.5: "x"}, {1.5: 1}, {"a": "x"}]),  # noqa: ARG005
    ("int key", lambda m: {1: str}, [{}, {1: "x"}, {1: 1}, {"a": "x"}]),  # noqa: ARG005
    ("bool key", lambda m: {True: str}, [{}, {True: "x"}, {True: 1}]),  # noqa: ARG005
    ("none key", lambda m: {None: str}, [{}, {None: "x"}, {None: 1}]),  # noqa: ARG005
    ("tuple key", lambda m: {(1, 2): str}, [{}, {(1, 2): "x"}]),  # noqa: ARG005
    ("type key", lambda m: {str: int}, [{}, {"a": 1}, {"a": "x"}]),  # noqa: ARG005
    ("int type key", lambda m: {int: str}, [{}, {1: "x"}, {1: 1}]),  # noqa: ARG005
    (
        "constant and named",
        lambda m: {1: str, "a": int},  # noqa: ARG005
        [{}, {1: "x"}, {"a": 1}, {1: "x", "a": 1}, {1: 1, "a": 1}],
    ),
    (
        "constant and catch-all",
        lambda m: {1: str, str: int},  # noqa: ARG005
        [{}, {1: "x"}, {1: "x", "b": 2}, {1: "x", "b": "z"}],
    ),
    # A construct written as a key is a schema, so it claims the keys it
    # matches. Reading it as a constant instead would declare a key the mapping
    # must carry, and the empty mapping would stop belonging.
    (
        "construct key",
        lambda m: {m.union(str, int): int},
        [{}, {"a": 1}, {1: 1}, {"a": "x"}],
    ),
    (
        "regex key",
        lambda m: {m.regex("[a-z]+"): int},
        [{}, {"ab": 1}, {"AB": 1}, {"ab": "x"}],
    ),
    (
        "construct key beside a named field",
        lambda m: {"a": int, m.union(str, int): str},
        [{}, {"a": 1}, {"a": 1, "b": "x"}, {"a": 1, "b": 2}],
    ),
]


@pytest.mark.parametrize(
    ("label", "build", "objects"), KEY_KINDS, ids=[k[0] for k in KEY_KINDS]
)
def test_a_constant_key_is_declared_and_a_schema_key_is_a_clause(
    label: str,
    build: Callable[[Any], object],
    objects: list[object],
) -> None:
    """A constant key must be present; a schema key only constrains what matches."""
    reference, layer = build(vt), build(vg)
    divergences = [
        (obj, _decide(vt, reference, obj), _decide(vg, layer, obj))
        for obj in objects
        if _decide(vt, reference, obj) != _decide(vg, layer, obj)
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
