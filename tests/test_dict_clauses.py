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
