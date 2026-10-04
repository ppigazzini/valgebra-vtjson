"""A class valgebra builds no validator for, written as a schema.

vtjson reads every class that is not a `TypedDict`, a `Protocol` or a
`NamedTuple` as an instance check and nothing more. valgebra reads more of some
classes and builds nothing for a few: the bare `typing.Union`, which from 3.14
is the class of every union object and which it reads as the typing form
instead, and a dataclass whose field annotations it reads and cannot -- a type
variable, a special form, a name that does not resolve. The layer still owes
vtjson's verdict, which never consulted the fields.

The axis is whether valgebra builds the class, crossed with the positions a
class can sit in. Beside it runs every class the typing runtime defines --
`typing`, `types` and `collections.abc` -- on its own, against values of many
kinds, which is the sweep that found `typing.Union`: a class valgebra starts
refusing in a later release shows here before it shows to a caller.
"""

from __future__ import annotations

import collections
import collections.abc
import dataclasses
import types
import typing
import warnings
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, TypeVar

import pytest
import typing_extensions
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


_T = TypeVar("_T")


def _dataclass(name: str, annotation: object) -> type:
    """Build a dataclass with one field ``a`` annotated ``annotation``.

    Frozen, so an instance hashes and can be probed as a dict key.
    """
    return dataclasses.make_dataclass(name, [("a", annotation)], frozen=True)


class _Class(NamedTuple):
    """A class valgebra builds nothing for, and an instance of it."""

    name: str
    cls: type
    instance: Callable[[], object]


_FIELDS: list[tuple[str, object]] = [
    ("a type variable", _T),
    ("a generic over a type variable", list[_T]),
    ("Final", typing.Final),
    ("Self", typing_extensions.Self),
    ("a name that does not resolve", "_Missing"),
]

CLASSES = [
    # A union object is its instance: `int | str` from 3.10, and `Union[int,
    # str]` as well from 3.14. Before 3.14 `typing.Union` is a special form
    # rather than a class, read as a callable by both libraries.
    _Class("typing.Union", typing.Union, lambda: int | str),
    *(
        _Class(f"a dataclass with a field of {label}", dc, lambda dc=dc: dc(1))
        for number, (label, annotation) in enumerate(_FIELDS)
        for dc in [_dataclass(f"_Field{number}", annotation)]
    ),
]


class _Attrs:
    """An object carrying one attribute, for the attribute-schema position."""

    def __init__(self, a: object) -> None:
        self.a = a

    def __repr__(self) -> str:
        return f"_Attrs({self.a!r})"


class _Position(NamedTuple):
    """A place a schema can put a class, and how a probe reaches it."""

    name: str
    wrap: Callable[[Any, object], object]
    lift: Callable[[object], object]


POSITIONS = [
    _Position("on its own", lambda _m, c: c, lambda v: v),
    _Position("a record's field", lambda _m, c: {"k": c}, lambda v: {"k": v}),
    _Position("a dict key", lambda _m, c: {c: int}, lambda v: {v: 1}),
    _Position("a list element", lambda _m, c: [c], lambda v: [v]),
    _Position("a repeated element", lambda _m, c: [c, ...], lambda v: [v, v]),
    _Position("a tuple element", lambda _m, c: (c,), lambda v: (v,)),
    _Position("Annotated metadata", lambda _m, c: Annotated[object, c], lambda v: v),
    _Position("a union's arm", lambda m, c: m.union(c, str), lambda v: v),
    _Position("an attribute schema", lambda m, c: m.fields({"a": c}), _Attrs),
    _Position("a generic argument", lambda _m, c: list[c], lambda v: [v]),  # ty: ignore[invalid-type-form]
]


@pytest.mark.parametrize("position", POSITIONS, ids=[p.name for p in POSITIONS])
@pytest.mark.parametrize("unbuilt", CLASSES, ids=[c.name for c in CLASSES])
def test_a_class_valgebra_does_not_build_decides_as_vtjson_does(
    unbuilt: _Class,
    position: _Position,
) -> None:
    """Every value reaches the same verdict, and the layer reaches one at all."""
    reference = position.wrap(vt, unbuilt.cls)
    layer = position.wrap(vg, unbuilt.cls)
    divergences = [
        (probe, a, b)
        for value in (unbuilt.instance(), 1, None, unbuilt.cls)
        if (a := _decide(vt, reference, probe := position.lift(value)))
        != (b := _decide(vg, layer, probe))
    ]
    assert not divergences, f"{unbuilt.name} as {position.name}: " + ", ".join(
        f"{probe!r} vtjson={a} layer={b}" for probe, a, b in divergences
    )


def _runtime_classes() -> list[Any]:
    """Return every class `typing`, `types` and `collections.abc` define."""
    seen: dict[type, str] = {}
    for module in (typing, types, collections.abc):
        for name in sorted(dir(module)):
            if name.startswith("_"):
                continue
            # A deprecated name warns when it is read, and reading every name is
            # the enumeration rather than a use of any one.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                cls = getattr(module, name)
            if isinstance(cls, type) and typing.get_origin(cls) is None:
                seen.setdefault(cls, f"{module.__name__}.{name}")
    return [pytest.param(cls, id=name) for cls, name in seen.items()]


def _values() -> list[object]:
    """Return values of many kinds, built fresh so none is consumed between runs."""
    return [
        1,
        1.5,
        None,
        "x",
        b"x",
        [1],
        (1,),
        {"a": 1},
        {1},
        range(2),
        collections.OrderedDict(),
        types.SimpleNamespace(),
        object(),
        len,
        int,
        int | str,
        typing.Union[int, str],  # noqa: UP007  (the spelling is the probe)
        typing.Optional[int],  # noqa: UP045  (the spelling is the probe)
        iter([]),
        (x for x in ()),
    ]


# A deprecated class -- `ByteString` -- is still a class both libraries read, and
# the warning each raises on asking `isinstance` of it is the class's own.
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.parametrize("cls", _runtime_classes())
def test_a_class_the_typing_runtime_defines_decides_as_vtjson_does(
    cls: type,
) -> None:
    """The instance check vtjson reads, whatever valgebra makes of the class."""
    divergences = [
        (value, a, b)
        for value in _values()
        if (a := _decide(vt, cls, value)) != (b := _decide(vg, cls, value))
    ]
    assert not divergences, ", ".join(
        f"{value!r} vtjson={a} layer={b}" for value, a, b in divergences
    )
