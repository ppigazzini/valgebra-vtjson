"""Construct semantics that differ from vtjson's for reasons the shape hides.

Each of these reads as correct until it is run against the oracle: a float
constant that vtjson matches approximately, a modular residue written the other
way round, a nullary construct spelled so that only one of its two accepted
forms works, and an ``ifthen`` whose explicit third argument means the opposite
of what translating it would suggest.

Both columns come from one builder, so a row cannot compare two schemas.
"""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable

# Inside vtjson's default relative tolerance of 1.5, and unequal to it.
NEAR = 1.5 + 1e-10
# Outside it.
FAR = 1.5 + 1e-8


def _decide(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


# A label, a builder run once per library, and the objects to probe.
ROWS: list[tuple[str, Callable[[Any], object], list[object]]] = [
    # A bare float constant. vtjson routes it through `close_to`, so a value
    # within the default relative tolerance belongs.
    ("float constant", lambda m: 1.5, [1.5, NEAR, FAR, 1.6, 1, "x", None]),  # noqa: ARG005
    ("float in a list", lambda m: [1.5], [[1.5], [NEAR], [FAR]]),  # noqa: ARG005
    ("float in a tuple", lambda m: (1.5,), [(1.5,), (NEAR,), (FAR,)]),  # noqa: ARG005
    ("float in a set", lambda m: {1.5}, [{1.5}, {NEAR}, {FAR}]),  # noqa: ARG005
    ("float as a field", lambda m: {"v": 1.5}, [{"v": 1.5}, {"v": NEAR}, {"v": FAR}]),  # noqa: ARG005
    ("float as a dict key", lambda m: {1.5: str}, [{1.5: "x"}, {NEAR: "x"}]),  # noqa: ARG005
    ("float under union", lambda m: m.union(1.5, str), [1.5, NEAR, FAR, "x"]),
    ("float under ifthen", lambda m: m.ifthen(float, 1.5), [1.5, NEAR, FAR, 1]),
    # `quote` opts out of the approximation on both sides.
    ("quote(float)", lambda m: m.quote(1.5), [1.5, NEAR, FAR]),
    # An int constant is exact in both.
    ("int constant", lambda m: 2, [2, 2.0000000001, 3]),  # noqa: ARG005
    # vtjson reads `Annotated` metadata as further schemas the value must also
    # satisfy, so a construct written there constrains rather than decorates.
    ("Annotated[int, ge(0)]", lambda m: Annotated[int, m.ge(0)], [1, 0, -1, "x"]),
    (
        "Annotated[int, ge, le]",
        lambda m: Annotated[int, m.ge(0), m.le(10)],
        [0, 5, 10, -1, 11],
    ),
    (
        "Annotated[str, regex]",
        lambda m: Annotated[str, m.regex("[a-z]+")],
        ["ab", "A", 1],
    ),
    (
        "dict[str, Annotated]",
        lambda m: dict[str, Annotated[int, m.ge(0)]],
        [{}, {"a": 1}, {"a": -1}, {"a": "x"}],
    ),
    (
        "list[Annotated]",
        lambda m: list[Annotated[int, m.ge(0)]],
        [[], [1], [-1], ["x"]],
    ),
    # A subscripted generic is a schema valgebra reads directly. Calling it
    # instead builds a container from the value, and a non-empty one is truthy.
    ("list[int]", lambda m: list[int], [[], [1], [1, "a"], "a", {"a": 1}, 1]),  # noqa: ARG005
    ("dict[str,int]", lambda m: dict[str, int], [{}, {"a": 1}, {"a": "x"}, "a"]),  # noqa: ARG005
    ("tuple[int,str]", lambda m: tuple[int, str], [(1, "a"), (1, 1), [1, "a"], "a"]),  # noqa: ARG005
    ("set[int]", lambda m: set[int], [set(), {1}, {"a"}, "a"]),  # noqa: ARG005
    # These typing forms are not callable, so they reached valgebra already.
    # `Optional` rather than `X | None`: the spelling is what is under test.
    ("Optional[int]", lambda m: Optional[int], [1, None, "a"]),  # noqa: ARG005, UP045
    ("Literal['a','b']", lambda m: Literal["a", "b"], ["a", "b", "c", 1]),  # noqa: ARG005
    # `Any` is a schema vtjson names outright, and it admits everything. Before
    # 3.11 it is not a class, so reading it by `isinstance(schema, type)` alone
    # drops it to the constant branch, where it admits only itself.
    ("Any", lambda m: Any, [1, "a", None, [], {"a": 1}, object()]),  # noqa: ARG005
    # `close_to` measures numbers vtjson recognises as such. A `Decimal` or a
    # `Fraction` compares fine under `math.isclose` and is not one of them.
    (
        "close_to(1.0)",
        lambda m: m.close_to(1.0),
        [1.0, 1, True, Decimal(1), Fraction(1, 1), complex(1, 0), "1", None],
    ),
    # A residue outside [0, divisor) is legal in vtjson and means what the
    # subtraction says, not what the modulo of the value says.
    ("div(3, -1)", lambda m: m.div(3, -1), [-1, 2, 5, 0, 1]),
    ("div(3, 4)", lambda m: m.div(3, 4), [1, 4, 7, 0, 2]),
    ("div(7, 7)", lambda m: m.div(7, 7), [0, 7, 14, 1]),
    ("div(-3, 1)", lambda m: m.div(-3, 1), [1, 4, -2, 0]),
    ("div(3, 1)", lambda m: m.div(3, 1), [1, 4, 7, 0, 2]),
    # Both spellings vtjson accepts for a nullary construct.
    ("bare float_", lambda m: m.float_, [1.0, 0.0, 5, True, "x", None]),
    ("called float_()", lambda m: m.float_(), [1.0, 0.0, 5, True, "x"]),
    ("bare number", lambda m: m.number, [1, 1.5, True, "x", None]),
    ("called number()", lambda m: m.number(), [1, 1.5, True, "x", None]),
    # An explicit `None` else-branch is vtjson's way of saying there is none.
    (
        "ifthen(int, str, None)",
        lambda m: m.ifthen(int, str, None),
        ["hi", 1.5, 5, None],
    ),
    ("ifthen(int, str)", lambda m: m.ifthen(int, str), ["hi", 1.5, 5, None]),
    ("ifthen with an else", lambda m: m.ifthen(int, str, bytes), ["hi", b"x", 5, 1.5]),
]


@pytest.mark.parametrize(("label", "build", "objects"), ROWS, ids=[r[0] for r in ROWS])
def test_the_construct_decides_as_vtjson_does(
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


def test_a_float_constant_stays_a_typed_singleton() -> None:
    """The tolerance widens which floats belong, not which types do.

    `docs/03-conformance.md` records that valgebra reads a constant as a
    typed singleton, so `1.0` admits no `int`. vtjson admits one, and that
    divergence is deliberate: reading a float as a tolerance must not quietly
    widen it into a cross-type match.
    """
    exactly_one = vg.compile(1.0)
    assert exactly_one.is_valid(1.0)
    assert exactly_one.is_valid(1.0 + 1e-12)
    assert not exactly_one.is_valid(1)
    assert not exactly_one.is_valid(True)
