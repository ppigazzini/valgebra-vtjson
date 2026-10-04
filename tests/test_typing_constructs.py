"""A typing construct written as a schema, in every position a schema can hold.

The typing runtime builds objects that name a type rather than being one: a type
variable, a `ParamSpec` and the `args` and `kwargs` it carries, a
`TypeVarTuple`, a forward reference. vtjson has no rule for any of them, so each
reaches the rule it applies to a schema it cannot place: neither a class nor
callable, it is a constant, and the schema admits only a value equal to it.
valgebra declines to read one as a literal of itself, so the layer decides that
equality rather than letting the refusal out.

The axis is position: the construct on its own, as a record's field, a dict key,
a sequence element, a set member, `Annotated` metadata, a union's arm, an
attribute schema and a generic argument. `P.args` reaches the translator by a
different arm from the rest, a subscripted generic whose origin is `P`, so a
position read by one arm and not the other shows here.
"""

from __future__ import annotations

import sys
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ForwardRef,
    NamedTuple,
    ParamSpec,
    Protocol,
    TypeVar,
)

import pytest
import typing_extensions
import vtjson as vt

import vtjson_compat as vg

if sys.version_info >= (3, 11):
    from typing import TypeVarTuple
else:
    from typing_extensions import TypeVarTuple

if TYPE_CHECKING:
    from collections.abc import Callable


def _decide(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


def _twin(construct: Callable[..., Any], name: str, *args: object, **kw: object) -> Any:
    """Build a second construct under a name another one already carries.

    A twin of the same name is what shows a comparison by name rather than by
    `!=`. Both checkers refuse the spelling written out, where the name and the
    variable differ, so it is built here by a call they do not special-case.
    """
    return construct(name, *args, **kw)


_T = TypeVar("_T")
_B = TypeVar("_B", bound=int)
_C = TypeVar("_C", int, str)
_E = typing_extensions.TypeVar("_E")
_P = ParamSpec("_P")
_Ts = TypeVarTuple("_Ts")
_P_TWIN = _twin(ParamSpec, "_P")


class _Form(NamedTuple):
    """A typing construct, and a distinct one built the same way.

    vtjson's `!=` decides the twin: a forward reference compares by the name it
    holds, `P.args` by its `P`, and the rest by identity.
    """

    name: str
    form: object
    twin: object


FORMS = [
    _Form("TypeVar", _T, _twin(TypeVar, "_T")),
    _Form("bound TypeVar", _B, _twin(TypeVar, "_B", bound=int)),
    _Form("constrained TypeVar", _C, _twin(TypeVar, "_C", int, str)),
    _Form("typing_extensions TypeVar", _E, _twin(typing_extensions.TypeVar, "_E")),
    _Form("ParamSpec", _P, _P_TWIN),
    _Form("ParamSpec args", _P.args, _P_TWIN.args),
    _Form("ParamSpec kwargs", _P.kwargs, _P_TWIN.kwargs),
    _Form("TypeVarTuple", _Ts, _twin(TypeVarTuple, "_Ts")),
    _Form("forward reference", ForwardRef("int"), ForwardRef("int")),
]


class _Attrs:
    """An object carrying one attribute, for the attribute-schema position."""

    def __init__(self, a: object) -> None:
        self.a = a

    def __repr__(self) -> str:
        return f"_Attrs({self.a!r})"


class _Position(NamedTuple):
    """A place a schema can put a form, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any, object], object]
    lift: Callable[[object], object]
    hashes: bool = False


POSITIONS = [
    _Position("on its own", lambda _m, c: c, lambda v: v),
    _Position("a record's field", lambda _m, c: {"k": c}, lambda v: {"k": v}),
    _Position("a dict key", lambda _m, c: {c: int}, lambda v: {v: 1}, hashes=True),
    _Position("a list element", lambda _m, c: [c], lambda v: [v]),
    _Position("a repeated element", lambda _m, c: [c, ...], lambda v: [v, v]),
    _Position("a tuple element", lambda _m, c: (c,), lambda v: (v,)),
    _Position("a set member", lambda _m, c: {c}, lambda v: {v}, hashes=True),
    _Position("Annotated metadata", lambda _m, c: Annotated[object, c], lambda v: v),
    _Position("a union's arm", lambda m, c: m.union(c, int), lambda v: v),
    _Position("an attribute schema", lambda m, c: m.fields({"a": c}), _Attrs),
    _Position("a generic argument", lambda _m, c: list[c], lambda v: [v]),  # ty: ignore[invalid-type-form]
]


def _values(form: _Form) -> list[object]:
    """Return the form, its twin, and values of other kinds."""
    return [form.form, form.twin, 1, None, "_T", type(form.form)]


def _hashable(form: object) -> bool:
    try:
        hash(form)
    except TypeError:
        return False
    return True


# `P.args` and `P.kwargs` define equality without a hash, so neither library can
# be handed one as a dict key or a set member: the schema cannot be written.
CASES = [
    pytest.param(form, position, id=f"{form.name}-{position.name}")
    for form in FORMS
    for position in POSITIONS
    if _hashable(form.form) or not position.hashes
]


@pytest.mark.parametrize(("form", "position"), CASES)
def test_a_typing_construct_decides_as_vtjson_does_wherever_it_is_written(
    form: _Form,
    position: _Position,
) -> None:
    """Every value reaches the same verdict, and the layer reaches one at all."""
    reference = position.wrap(vt, form.form)
    layer = position.wrap(vg, form.form)
    divergences = [
        (probe, a, b)
        for value in _values(form)
        if (a := _decide(vt, reference, probe := position.lift(value)))
        != (b := _decide(vg, layer, probe))
    ]
    assert not divergences, f"{form.name} as {position.name}: " + ", ".join(
        f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences
    )


class _Holds(Protocol[_T]):
    a: _T


@pytest.mark.parametrize(
    "obj",
    [_Attrs(_T), _Attrs(1), _Attrs(None), object()],
    ids=["holds T", "holds 1", "holds None", "no attribute"],
)
def test_a_generic_protocol_reads_its_type_variable_as_vtjson_does(
    obj: object,
) -> None:
    """A `Protocol[T]` declaring `a: T` holds `a` to the type variable itself."""
    assert _decide(vg, _Holds, obj) == _decide(vt, _Holds, obj)


class _AnswersBoth:
    """Equal and unequal to everything at once."""

    def __eq__(self, other: object) -> bool:
        return True

    def __ne__(self, other: object) -> bool:
        return True

    __hash__ = object.__hash__


class _AnswersNeither:
    """Neither equal nor unequal to anything."""

    def __eq__(self, other: object) -> bool:
        return False

    def __ne__(self, other: object) -> bool:
        return False

    __hash__ = object.__hash__


@pytest.mark.parametrize(
    "obj", [_AnswersBoth(), _AnswersNeither()], ids=["both", "neither"]
)
def test_a_typing_construct_is_compared_by_the_question_vtjson_asks(
    obj: object,
) -> None:
    """A value answering `!=` is refused, whatever it answers to `==`."""
    assert _decide(vg, _T, obj) == _decide(vt, _T, obj)
