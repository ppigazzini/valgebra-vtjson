"""The layer's call surface is vtjson's, argument names included.

A drop-in replacement is only one for the calls people actually write. Renaming
a parameter keeps every positional call working and breaks every keyword call,
and vtjson's own documentation writes several of these by keyword. Nothing else
in this suite can see it: the differential rows all call positionally, and the
parity inventory checks that vtjson's *names* exist here, never their
signatures.

The surface diverges in both directions — arguments this layer added, and
arguments it dropped — so the comparison is an equality, not a subset test.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest
import vtjson as vt

import vtjson_compat as vg

# Names whose call shape differs for a stated reason.
#
# `anything` and `nothing` are classes in vtjson and validator constants here.
# Both are written without parentheses wherever they appear as a schema, so no
# call can distinguish them. The error types are exception classes, whose
# signature is Python's rather than either library's.
EXEMPT = frozenset({"anything", "nothing", "ValidationError", "SchemaError"})


# A variadic parameter has no name a caller can use, so its spelling cannot
# break a call and is not part of the surface under test.
_BY_KEYWORD = frozenset(
    {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
)


def _parameters(obj: Any) -> list[str] | None:
    """Return the names ``obj`` accepts by keyword, or ``None`` if it has none."""
    target = obj.__init__ if isinstance(obj, type) else obj
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return None
    return [
        name
        for name, parameter in signature.parameters.items()
        if name != "self" and parameter.kind in _BY_KEYWORD
    ]


def _comparable() -> list[str]:
    """Return every public name whose signature both libraries expose."""
    return sorted(
        name
        for name in vg.__all__
        if name not in EXEMPT
        and hasattr(vt, name)
        and _parameters(getattr(vt, name)) is not None
        and _parameters(getattr(vg, name)) is not None
    )


def test_the_comparison_covers_the_surface() -> None:
    """Guard the guard: an empty comparison would pass silently."""
    covered = _comparable()
    assert len(covered) > len(vg.__all__) // 2, (
        f"only {len(covered)} of {len(vg.__all__)} public names are comparable"
    )


@pytest.mark.parametrize("name", _comparable())
def test_the_parameter_names_are_vtjson_s(name: str) -> None:
    """A call vtjson accepts by keyword is one this layer accepts by keyword."""
    assert _parameters(getattr(vg, name)) == _parameters(getattr(vt, name)), (
        f"{name}: vtjson takes {_parameters(getattr(vt, name))}, "
        f"the layer takes {_parameters(getattr(vg, name))}"
    )


# A call written the way vtjson's own documentation writes it.
BY_KEYWORD: list[tuple[str, Any]] = [
    ("ge(lb=…)", lambda m: m.ge(lb=5)),
    ("le(ub=…)", lambda m: m.le(ub=5)),
    ("interval(lb=…, ub=…)", lambda m: m.interval(lb=1, ub=10)),
    ("size(lb=…)", lambda m: m.size(lb=2)),
    ("regex(regex=…)", lambda m: m.regex(regex="a.*")),
    ("quote(schema=…)", lambda m: m.quote(schema=1)),
    ("fields(d=…)", lambda m: m.fields(d={"a": int})),
    (
        "ifthen(if_schema=…, then_schema=…)",
        lambda m: m.ifthen(if_schema=int, then_schema=str),
    ),
    ("make_type(subs=…)", lambda m: m.make_type(int, subs={})),
    ("optional_key(key, _optional)", lambda m: m.optional_key("a", True)),
]


@pytest.mark.parametrize(
    ("label", "call"), BY_KEYWORD, ids=[row[0] for row in BY_KEYWORD]
)
def test_a_keyword_call_vtjson_accepts_is_accepted(label: str, call: Any) -> None:
    """The call reaches the construct instead of a `TypeError`."""
    call(vt)
    call(vg)


def test_an_argument_vtjson_does_not_have_is_refused() -> None:
    """A surface wider than vtjson's is a surface that does not port back.

    `cond` takes cases and nothing else. Accepting a `default` keyword makes a
    schema that runs here and fails to build under vtjson, which is the same
    defect as a missing argument pointed the other way.
    """
    # The checker is right that neither takes this argument. That is the
    # assertion.
    with pytest.raises(TypeError):
        vt.cond((int, str), default=str)  # ty: ignore[unknown-argument]
    with pytest.raises(TypeError):
        vg.cond((int, str), default=str)  # ty: ignore[unknown-argument]


def test_optional_key_can_declare_a_required_key() -> None:
    """`_optional=False` names a key that must be present, as in vtjson."""

    def accepts(module: Any, optional: bool) -> bool:  # noqa: FBT001
        schema = {module.optional_key("a", optional): int}
        try:
            module.validate(schema, {})
        except module.ValidationError:
            return False
        return True

    assert accepts(vt, optional=True) == accepts(vg, optional=True)
    assert accepts(vt, optional=False) == accepts(vg, optional=False)
    assert accepts(vg, optional=True)
    assert not accepts(vg, optional=False)


def test_make_type_refuses_a_substitution_it_cannot_perform() -> None:
    """An accepted `subs` that did nothing would validate against the wrong schema."""
    assert isinstance(vg.make_type(int, subs={}), type)
    with pytest.raises(NotImplementedError):
        vg.make_type(int, subs={"x": str})
