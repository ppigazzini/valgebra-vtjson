"""Differential parity across each construct's *argument* space.

``test_differential.py`` crosses constructs with objects, holding each
construct's arguments at one shape. This module crosses the arguments
themselves: the sentinel forms vtjson accepts (``...`` for an unbounded end),
the boundary arities (no candidates, one, several), and the values a construct
is asked about but cannot apply its operator to.

Both columns are built from one argument tuple, so a row cannot drift into
testing two different schemas.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable


# The two libraries are addressed through the surface they share — `validate`
# and the construct factories — which no single static type names, so the module
# a row is applied to is `Any`.
def _accepts(module: Any, schema: object, obj: object) -> bool:
    """Whether ``module`` accepts ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj)
    except (vt.ValidationError, vg.ValidationError):
        return False
    return True


class _Longest:
    """A sized value at the longest length `len` can answer."""

    def __len__(self) -> int:
        return sys.maxsize


_MAX = sys.maxsize
# A value of each length a bound around `sys.maxsize` can tell apart, one with
# no length at all, and an empty one.
_SIZED: list[object] = ["", "a", [1], {}, 1, None, _Longest()]


# Each row: a label, a builder taking the module and returning the schema, and
# the objects to probe. The builder runs once per library, so the two schemas
# are the same construct with the same arguments in each library's own spelling.
ARGUMENT_SPACE: list[tuple[str, Callable[[Any], object], list[object]]] = [
    # An unbounded end. vtjson reads `...` as "no bound on this side".
    ("interval(1, ...)", lambda m: m.interval(1, ...), [0, 1, 2, 10**9]),
    ("interval(..., 5)", lambda m: m.interval(..., 5), [-(10**9), -10, 5, 6]),
    ("interval(..., ...)", lambda m: m.interval(..., ...), [-1, 0, 10**9]),
    ("interval(1, 5)", lambda m: m.interval(1, 5), [0, 1, 5, 6]),
    # `size` takes the same sentinel, and is the construct that reads it today.
    ("size(2, ...)", lambda m: m.size(2, ...), ["a", "ab", "abcdef"]),
    ("size(3)", lambda m: m.size(3), ["ab", "abc", "abcd"]),
    # A length past `sys.maxsize` is one `len` cannot answer. Each end is
    # compared as any other, so a lower one admits nothing and an upper one
    # bounds nothing, whatever the valgebra node takes.
    ("size(MAX)", lambda m: m.size(_MAX), _SIZED),
    ("size(MAX + 1)", lambda m: m.size(_MAX + 1), _SIZED),
    ("size(2**64)", lambda m: m.size(2**64), _SIZED),
    ("size(2**70)", lambda m: m.size(2**70), _SIZED),
    ("size(MAX + 1, ...)", lambda m: m.size(_MAX + 1, ...), _SIZED),
    ("size(2**70, ...)", lambda m: m.size(2**70, ...), _SIZED),
    ("size(0, MAX)", lambda m: m.size(0, _MAX), _SIZED),
    ("size(0, MAX + 1)", lambda m: m.size(0, _MAX + 1), _SIZED),
    ("size(0, 2**64)", lambda m: m.size(0, 2**64), _SIZED),
    ("size(1, 2**70)", lambda m: m.size(1, 2**70), _SIZED),
    ("size(MAX, MAX + 1)", lambda m: m.size(_MAX, _MAX + 1), _SIZED),
    ("size(MAX + 1, MAX + 2)", lambda m: m.size(_MAX + 1, _MAX + 2), _SIZED),
    # The dict-key modifiers, over arities and over values `in` cannot apply to.
    ("keys('a')", lambda m: m.keys("a"), [{"a": 1}, {}, 5, "x", None, ["a"]]),
    ("keys()", lambda m: m.keys(), [{}, {"a": 1}, 5, None]),
    (
        "one_of('a','b')",
        lambda m: m.one_of("a", "b"),
        [{"a": 1}, {"a": 1, "b": 2}, {}, 5, None],
    ),
    ("at_least_one_of('a')", lambda m: m.at_least_one_of("a"), [{"a": 1}, {}, 5, None]),
    (
        "at_most_one_of('a')",
        lambda m: m.at_most_one_of("a"),
        [{"a": 1}, {}, 5, "x", None],
    ),
    (
        "at_most_one_of('a','b')",
        lambda m: m.at_most_one_of("a", "b"),
        [{"a": 1, "b": 2}, {}, 5, None],
    ),
    # Remaining constructs at their sentinel and boundary arguments.
    ("div(3, 1)", lambda m: m.div(3, 1), [3, 4, 7, False]),
    (
        "regex('a+', fullmatch=False)",
        lambda m: m.regex("a+", fullmatch=False),
        ["aaa", "aab", "baa", ""],
    ),
    ("ip_address(4)", lambda m: m.ip_address(4), ["1.2.3.4", "::1", 5, "x"]),
]


@pytest.mark.parametrize(
    ("label", "build", "objects"),
    ARGUMENT_SPACE,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_argument_shapes_reach_the_same_decision(
    label: str,
    build: Callable[[Any], object],
    objects: list[object],
) -> None:
    """Each construct decides as vtjson does at every argument shape probed."""
    reference = build(vt)
    layer = build(vg)
    divergences = [
        (obj, _accepts(vt, reference, obj), _accepts(vg, layer, obj))
        for obj in objects
        if _accepts(vt, reference, obj) != _accepts(vg, layer, obj)
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
