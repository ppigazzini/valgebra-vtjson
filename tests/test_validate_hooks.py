"""An object carrying vtjson's ``__validate__`` hook, written as a schema.

vtjson asks ``hasattr(schema, "__validate__")`` before any other question but
whether the schema is one of its own, and an object answering it is validated by
calling ``schema.__validate__(obj, name=..., strict=..., subs=...)``: the empty
string is a pass and any other answer a failure. The hook outranks every reading
of a class, so a dataclass or a `NamedTuple` carrying one is read by the hook
alone.

The axis is what carries the hook -- a class holding a static method, a class
method or a plain one, an instance, a class that is also a dataclass or a
`NamedTuple`, an object whose `__getattr__` supplies it, and hooks answering
something other than a string -- crossed with the positions a schema can sit
in, laxness among them, since vtjson hands the hook the strictness in force.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable


def _decide(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``, or that it raised."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    except Exception:  # noqa: BLE001  (the crash is the answer being compared)
        return "raise"
    return "accept"


def _agree(reference: str, layer: str) -> bool:
    """Whether the layer reached vtjson's verdict, or rejected where it crashed.

    A hook answering something other than a string is a failure to vtjson
    wherever it compares the answer, and crashes it wherever it joins the answer
    into a message: a record's field, a union's arm. The ledger's row for the
    hook names that direction.
    """
    return reference == layer or (reference == "raise" and layer == "reject")


def _seven(obj: object, strict: bool) -> str:  # noqa: FBT001
    """Pass ``7``, and anything at all when the hook is told it is lax."""
    return "" if obj == 7 or not strict else f"{obj!r} is not 7"


class _Static:
    @staticmethod
    def __validate__(obj: object, name: str, strict: bool, subs: object) -> str:  # noqa: FBT001
        return _seven(obj, strict)


class _Classmethod:
    @classmethod
    def __validate__(cls, obj: object, name: str, strict: bool, subs: object) -> str:  # noqa: FBT001
        return _seven(obj, strict)


class _Plain:
    # Read off the class, the method is a plain function and the value binds to
    # its first parameter. vtjson calls it so, and so does the layer.
    def __validate__(self, name: str, strict: bool, subs: object) -> str:  # noqa: FBT001
        return _seven(self, strict)


class _Instance:
    def __validate__(self, obj: object, name: str, strict: bool, subs: object) -> str:  # noqa: FBT001
        return _seven(obj, strict)

    def __repr__(self) -> str:
        return "_Instance()"


@dataclasses.dataclass(frozen=True)
class _Dataclass:
    a: int

    @staticmethod
    def __validate__(obj: object, name: str, strict: bool, subs: object) -> str:  # noqa: FBT001
        return _seven(obj, strict)


class _Tuple(NamedTuple):
    a: int

    @staticmethod
    def __validate__(obj: object, name: str, strict: bool, subs: object) -> str:  # noqa: FBT001
        return _seven(obj, strict)


class _Supplied:
    """An object whose `__getattr__` answers every name, the hook's among them."""

    def __getattr__(self, name: str) -> Callable[..., str]:
        return lambda obj, name, strict, subs: _seven(obj, strict)  # noqa: ARG005

    def __repr__(self) -> str:
        return "_Supplied()"


class _AnswersNone:
    @staticmethod
    def __validate__(obj: object, name: str, strict: bool, subs: object) -> None:  # noqa: FBT001
        return None


class _AnswersFalse:
    @staticmethod
    def __validate__(obj: object, name: str, strict: bool, subs: object) -> bool:  # noqa: FBT001
        return False


CARRIERS: list[tuple[str, object]] = [
    ("a static method", _Static),
    ("a class method", _Classmethod),
    ("a plain method read off the class", _Plain),
    ("an instance", _Instance()),
    ("a dataclass", _Dataclass),
    ("a NamedTuple", _Tuple),
    ("__getattr__", _Supplied()),
    ("a hook answering None", _AnswersNone),
    ("a hook answering False", _AnswersFalse),
]


class _Position(NamedTuple):
    """A place a schema can put a hook, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any, object], object]
    lift: Callable[[object], object]


POSITIONS = [
    _Position("on its own", lambda _m, c: c, lambda v: v),
    _Position("a record's field", lambda _m, c: {"k": c}, lambda v: {"k": v}),
    _Position("a lax record's field", lambda m, c: m.lax({"k": c}), lambda v: {"k": v}),
    _Position("a dict key", lambda _m, c: {c: int}, lambda v: {v: 1}),
    _Position("a list element", lambda _m, c: [c], lambda v: [v]),
    _Position("a lax list element", lambda m, c: m.lax([c]), lambda v: [v]),
    _Position("a set member", lambda _m, c: {c}, lambda v: {v}),
    _Position("a lax set member", lambda m, c: m.lax({c}), lambda v: {v}),
    _Position("strict inside lax", lambda m, c: m.lax(m.strict(c)), lambda v: v),
    _Position(
        "a label inside lax", lambda m, c: m.lax(m.set_label(c, "L")), lambda v: v
    ),
    _Position("Annotated metadata", lambda _m, c: Annotated[object, c], lambda v: v),
    _Position("a union's arm", lambda m, c: m.union(c, str), lambda v: v),
    _Position("a lax union's arm", lambda m, c: m.lax(m.union(c, str)), lambda v: v),
]

VALUES: list[object] = [7, 8, None, "7", 7.0]


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize(("label", "carrier"), CARRIERS, ids=[c[0] for c in CARRIERS])
def test_a_validate_hook_decides_as_vtjson_does_wherever_it_is_written(
    label: str,
    carrier: object,
    position: _Position,
) -> None:
    """Every value reaches the same verdict under both libraries."""
    reference = position.wrap(vt, carrier)
    layer = position.wrap(vg, carrier)
    divergences = [
        (probe, a, b)
        for value in VALUES
        if not _agree(
            a := _decide(vt, reference, probe := position.lift(value)),
            b := _decide(vg, layer, probe),
        )
    ]
    assert not divergences, f"{label} as {position.name}: " + ", ".join(
        f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences
    )


@pytest.mark.parametrize(("label", "carrier"), CARRIERS, ids=[c[0] for c in CARRIERS])
def test_a_validate_hook_is_told_the_strictness_validate_was_asked_for(
    label: str,
    carrier: object,
) -> None:
    """``validate(strict=False)`` reaches the hook as ``strict=False``."""

    def decide(module: Any, obj: object) -> str:
        try:
            module.validate(carrier, obj, strict=False)
        except module.ValidationError:
            return "reject"
        return "accept"

    assert [decide(vg, v) for v in VALUES] == [decide(vt, v) for v in VALUES], label
