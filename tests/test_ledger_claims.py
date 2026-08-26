"""The ledger's checkable claims, checked.

A differences ledger is prose a reader is asked to trust, and most of its rows
are about intent. Some are measurements — how deep a schema may nest, and what a
recommended shape costs — and a measurement in prose that nothing re-runs is a
number that was true once.

These pin the depth rows. The limit belongs to valgebra rather than to this
layer, so a valgebra release can move it; that is the point of measuring here
rather than quoting.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable

_LEDGER = (
    Path(__file__).resolve().parent.parent / "docs" / "03-conformance.md"
).read_text(encoding="utf-8")

# Far past any bound, so a shape that never refuses fails rather than hangs.
_CEILING = 300


def _first_refused_depth(wrap: Callable[[Any], Any]) -> int:
    """Return the nesting depth at which the translator first refuses ``wrap``."""
    schema: Any = int
    for depth in range(1, _CEILING):
        schema = wrap(schema)
        try:
            vg.compile(schema)
        except Exception:  # noqa: BLE001  (any refusal is the bound being hit)
            return depth
    pytest.fail(f"no depth below {_CEILING} was refused")
    return _CEILING  # pragma: no cover - pytest.fail does not return


SHAPES: list[tuple[str, Callable[[Any], Any]]] = [
    ("a one-element list", lambda inner: [inner]),
    ("a homogeneous list", lambda inner: [inner, ...]),
]


@pytest.mark.parametrize(("label", "wrap"), SHAPES, ids=[s[0] for s in SHAPES])
def test_the_ledger_names_the_depth_each_shape_reaches(
    label: str, wrap: Callable[[Any], Any]
) -> None:
    """A shape the ledger recommends is one whose cost it states."""
    depth = _first_refused_depth(wrap)
    assert str(depth) in _LEDGER, (
        f"{label} is refused at {depth} levels and docs/03-conformance.md does "
        f"not say so; a reader choosing between shapes needs both numbers"
    )


def test_the_recommended_shape_is_the_deeper_one() -> None:
    """The migration note is only advice if the shape it names goes deeper."""
    assert _first_refused_depth(lambda inner: [inner, ...]) > _first_refused_depth(
        lambda inner: [inner]
    )
