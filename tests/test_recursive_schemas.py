"""A schema that contains itself denotes the least set closed under its body.

vtjson compiles a schema object it is already compiling into a back edge, so a
dict holding itself is a recursive schema rather than an infinite descent. The
set it denotes is the *least* fixpoint: a shape reachable only by infinite
nesting has no finite member, so `x = [x]` admits nothing at all.

Recursion by self-reference is not the labelled mechanism. `set_label` plus
validate-time `subs` is a different feature, and a dict that simply contains
itself uses none of it.
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


def _tree() -> dict[object, object]:
    """Return a record whose children are records of the same shape."""
    node: dict[object, object] = {}
    node.update({"v": int, "kids": [node, ...]})
    return node


def _mutual() -> dict[object, object]:
    """Return two records that reach each other, so neither closes alone."""
    first: dict[object, object] = {}
    second: dict[object, object] = {}
    first.update({"b": second})
    second.update({"a?": first, "v": int})
    return first


def _self_list() -> list[object]:
    """Return a one-element list whose element is the list itself.

    Contractive — the reference is under a constructor — and satisfied by no
    finite value, so the least fixpoint is empty.
    """
    inner: list[object] = []
    inner.append(inner)
    return inner


def _self_value() -> dict[object, object]:
    """Return a record whose only field is itself — empty, for the same reason."""
    node: dict[object, object] = {}
    node.update({"self": node})
    return node


def _nested_tree() -> dict[object, object]:
    """Return a recursive record reached through a container that is not one."""
    return {"root": _tree(), "count": int}


ROWS: list[tuple[str, Callable[[], object], list[object]]] = [
    (
        "self-referential record",
        _tree,
        [
            {"v": 1, "kids": []},
            {"v": 1, "kids": [{"v": 2, "kids": []}]},
            {"v": 1, "kids": [{"v": 2, "kids": [{"v": 3, "kids": []}]}]},
            {"v": "x", "kids": []},
            {"v": 1, "kids": [{"v": "x", "kids": []}]},
            {"v": 1},
            {},
            1,
        ],
    ),
    (
        "mutually recursive records",
        _mutual,
        [
            {"b": {"v": 1}},
            {"b": {"v": 1, "a": {"b": {"v": 2}}}},
            {"b": {"v": "x"}},
            {"b": {}},
            {},
        ],
    ),
    ("self-referential list", _self_list, [[], [[]], [[[]]], [1], 1]),
    ("record holding only itself", _self_value, [{"self": {}}, {}, 1]),
    (
        "recursive record inside another",
        _nested_tree,
        [
            {"root": {"v": 1, "kids": []}, "count": 2},
            {"root": {"v": 1, "kids": [{"v": 2, "kids": []}]}, "count": 2},
            {"root": {"v": "x", "kids": []}, "count": 2},
            {"count": 2},
        ],
    ),
]


@pytest.mark.parametrize(("label", "build", "objects"), ROWS, ids=[r[0] for r in ROWS])
def test_a_self_referential_schema_decides_as_vtjson_does(
    label: str,
    build: Callable[[], object],
    objects: list[object],
) -> None:
    """Every probe reaches the same verdict, and neither side overflows."""
    divergences = [
        (obj, a, b)
        for obj in objects
        if (a := _decide(vt, build(), obj)) != (b := _decide(vg, build(), obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


@pytest.mark.parametrize("wrapper", ["lax", "strict"])
def test_strictness_reaches_a_recursive_record(wrapper: str) -> None:
    """A back edge carries the mode the rest of the subtree was built with."""
    probes: list[object] = [
        {"v": 1, "kids": []},
        {"v": 1, "kids": [], "extra": 9},
        {"v": 1, "kids": [{"v": 2, "kids": [], "extra": 9}]},
    ]
    divergences = [
        (obj, a, b)
        for obj in probes
        if (a := _decide(vt, getattr(vt, wrapper)(_tree()), obj))
        != (b := _decide(vg, getattr(vg, wrapper)(_tree()), obj))
    ]
    assert not divergences, f"{wrapper}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
