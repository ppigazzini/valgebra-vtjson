"""What `lax` and `strict` do to a dict that has a catch-all.

vtjson decides a key by the clauses that claim it, and strictness only settles
what happens to a key **no** clause claims: `strict` rejects it, `lax` admits it.
A typed catch-all is a clause either way, so neither mode may discard it.

Reaching that through `Validator.open`/`close` cannot work — `open` adds a clause
matching every key, which subsumes the typed one, and `close` drops the typed one
outright. Both lose the constraint the schema was written to carry.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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

ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
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
