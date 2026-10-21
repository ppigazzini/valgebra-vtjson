"""Which fields a structural class requires, and what each one admits.

vtjson reads a class's hints with their qualifiers kept, and decides presence
the way its `_to_dict` does: in a class whose `__total__` is true a field is
required unless its hint is `NotRequired[...]`, and in one whose `__total__` is
false it is optional unless its hint is `Required[...]`. Only `typing`'s
qualifiers are read, and only at the top of a hint; each is stripped, and what
it wraps is the field's schema, `Annotated` metadata included. The class's own
`__total__` decides every field it has, inherited ones too, so a field a total
base declares is optional in a subclass declared `total=False`, whatever
`__required_keys__` says. A field's name is taken as written, so a name ending
in `?` is a required key ending in `?`.

A qualifier vtjson does not read for presence stays in the field's schema:
`ReadOnly`, a `Required` or `NotRequired` inside `Annotated` or inside another
qualifier, and `typing_extensions`' own on a release whose `typing` lacks it.
vtjson calls it there, as it calls any qualifier written outside a class, and
the call raises, so the field admits nothing.

The axis is the field's qualifier crossed with the class's totality and its
inheritance, with the module whose `TypedDict` builds the class, and with each
reading that sees the class: the class written as a schema, `protocol(cls,
dict=True)` against a mapping's items, `protocol(cls)` against an object's
attributes, and the first two under `lax`. A class that is not a `TypedDict`
carries no `__total__`, so its fields are required unless a hint says
otherwise; a `Protocol` and a `NamedTuple` written as a schema are read by their
attributes. Neither library recognises `typing_extensions`' `TypedDict` as one,
so written as a schema it is a class like any other, which both read alike.

vtjson reads an optional attribute the value lacks anyway, and `getattr` raises
out of `validate`; the layer rejects the value, the direction the ledger allows,
and the rows count that as agreement.
"""

from __future__ import annotations

import typing
from types import SimpleNamespace
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, Protocol, TypedDict

import pytest
import typing_extensions
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable

# `Required` and `NotRequired` reach `typing` in 3.11, and vtjson reads no
# other module's, so the rows that carry one run from there.
Required: Any = getattr(typing, "Required", None)
NotRequired: Any = getattr(typing, "NotRequired", None)


def _outcome(module: Any, schema: object, obj: object) -> str:
    """Return ``module``'s verdict on ``obj`` against ``schema``, or that it raised."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    except Exception:  # noqa: BLE001  (vtjson lets a value's exception out)
        return "raise"
    return "accept"


def _agree(reference: str, layer: str) -> bool:
    """Whether the layer reaches vtjson's verdict, or rejects where it raised."""
    return reference == layer or (reference == "raise" and layer == "reject")


def _hints(m: Any) -> dict[str, object]:
    """Return each hint a field can carry, built in a library ``m``."""
    natural = m.ge(0)
    hints: dict[str, object] = {
        "int": int,
        "Annotated[int, ge(0)]": Annotated[int, natural],
    }
    if Required is not None:
        hints |= {
            "Required[int]": Required[int],
            "NotRequired[int]": NotRequired[int],
            "Required[Annotated[int, ge(0)]]": Required[Annotated[int, natural]],
            "NotRequired[Annotated[int, ge(0)]]": NotRequired[Annotated[int, natural]],
            "Annotated[NotRequired[int], ge(0)]": Annotated[NotRequired[int], natural],
            "ReadOnly[NotRequired[int]]": typing_extensions.ReadOnly[NotRequired[int]],
            "NotRequired[ReadOnly[int]]": NotRequired[typing_extensions.ReadOnly[int]],
        }
    # `typing_extensions`' qualifiers are `typing`'s from the release that
    # defines each there, and a class of their own before it.
    hints |= {
        f"typing_extensions.{name}[int]": getattr(typing_extensions, name)[int]
        for name in ("Required", "NotRequired", "ReadOnly")
    }
    return hints


# Each module whose `TypedDict` builds a class.
MAKERS: list[tuple[str, Any]] = [
    ("typing", TypedDict),
    ("typing_extensions", typing_extensions.TypedDict),
]


def _typed_dicts(m: Any, maker: Any) -> dict[str, type]:
    """Return a `TypedDict` per hint and totality, and the inheritance shapes."""
    classes: dict[str, type] = {
        f"a: {name}, total={total}": maker("_Row", {"a": hint, "b": str}, total=total)
        for name, hint in _hints(m).items()
        for total in (True, False)
    }
    classes["a field named a?"] = maker("_Marked", {"a?": int, "b": str})
    base_partial = maker("_Partial", {"a": int}, total=False)
    base_whole = maker("_Whole", {"a": int})
    classes["total over total=False"] = type(
        "_OnPartial", (base_partial,), {"__annotations__": {"b": str}}
    )
    classes["total=False over total"] = _subclass(base_whole, {"b": str})
    if Required is not None:
        base_optional = maker("_WholeOptional", {"a": NotRequired[int]})
        classes["total=False over NotRequired"] = _subclass(
            base_optional, {"b": Required[str]}
        )
    return classes


def _subclass(base: type, annotations: dict[str, object]) -> type:
    """Return a `total=False` subclass of ``base`` declaring ``annotations``."""
    return type(base)("_OnBase", (base,), {"__annotations__": annotations}, total=False)


def _attribute_classes(m: Any) -> dict[str, type]:
    """Return a plain class and a `Protocol` per hint, read by their attributes."""
    classes: dict[str, type] = {}
    for name, hint in _hints(m).items():
        annotations = {"__annotations__": {"a": hint, "b": str}}
        classes[f"plain, a: {name}"] = type("_Plain", (), annotations)
        classes[f"Protocol, a: {name}"] = type("_Shape", (Protocol,), annotations)
    return classes


ITEMS: list[object] = [
    {},
    {"a": 1},
    {"a": -1},
    {"a": "x"},
    {"b": "y"},
    {"a": 1, "b": "y"},
    {"a": -1, "b": "y"},
    {"a": 1, "b": 2},
    {"a": 1, "b": "y", "c": 0},
    {"a?": 1, "b": "y"},
    {"a?": "x", "b": "y"},
]

ATTRIBUTES: list[object] = [
    SimpleNamespace(),
    SimpleNamespace(a=1),
    SimpleNamespace(b="y"),
    SimpleNamespace(a=1, b="y"),
    SimpleNamespace(a=-1, b="y"),
    SimpleNamespace(a="x", b="y"),
    SimpleNamespace(a=1, b=2),
]

# Each reading of a `TypedDict`, the values it is asked about, and its spelling.
TYPED_DICT_READINGS: list[tuple[str, list[object], Callable[[Any, type], object]]] = [
    ("as a schema", ITEMS, lambda _m, cls: cls),
    ("under lax", ITEMS, lambda m, cls: m.lax(cls)),
    ("protocol(dict=True)", ITEMS, lambda m, cls: m.protocol(cls, dict=True)),
    (
        "lax protocol(dict=True)",
        ITEMS,
        lambda m, cls: m.lax(m.protocol(cls, dict=True)),
    ),
    ("protocol()", ATTRIBUTES, lambda m, cls: m.protocol(cls)),
]

# Each reading of a class that is not a `TypedDict`. A `Protocol` written as a
# schema is `protocol` of it; a plain class written as one is an instance check,
# which reads no field, so it is not crossed here.
ATTRIBUTE_READINGS: list[tuple[str, list[object], Callable[[Any, type], object]]] = [
    ("protocol()", ATTRIBUTES, lambda m, cls: m.protocol(cls)),
    ("protocol(dict=True)", ITEMS, lambda m, cls: m.protocol(cls, dict=True)),
    ("as a schema", ATTRIBUTES, lambda _m, cls: cls),
]


def _divergences(
    build: Callable[[Any], object], values: list[object]
) -> list[tuple[object, str, str]]:
    """Return each value whose verdict differs, with both verdicts."""
    reference, layer = build(vt), build(vg)
    return [
        (obj, a, b)
        for obj in values
        if not _agree(a := _outcome(vt, reference, obj), b := _outcome(vg, layer, obj))
    ]


TYPED_DICT_CASES = [
    pytest.param(maker, label, *reading, id=f"{name}-{label}-{reading[0]}")
    for name, maker in MAKERS
    for label in _typed_dicts(vt, maker)
    for reading in TYPED_DICT_READINGS
]


@pytest.mark.parametrize(
    ("maker", "label", "reading", "values", "spell"), TYPED_DICT_CASES
)
def test_a_typed_dict_reads_its_fields_as_vtjson_does(
    maker: Any,
    label: str,
    reading: str,
    values: list[object],
    spell: Callable[[Any, type], object],
) -> None:
    """Each field is required, or not, and admits what vtjson's field admits."""
    divergences = _divergences(
        lambda m: spell(m, _typed_dicts(m, maker)[label]), values
    )
    assert not divergences, f"{label}, {reading}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


ATTRIBUTE_CASES = [
    pytest.param(label, *reading, id=f"{label}-{reading[0]}")
    for label in _attribute_classes(vt)
    for reading in ATTRIBUTE_READINGS
    if reading[0] != "as a schema" or label.startswith("Protocol")
]


@pytest.mark.parametrize(("label", "reading", "values", "spell"), ATTRIBUTE_CASES)
def test_a_class_reads_its_hints_as_vtjson_does(
    label: str,
    reading: str,
    values: list[object],
    spell: Callable[[Any, type], object],
) -> None:
    """A class's hints are read with their qualifiers and their metadata."""
    divergences = _divergences(lambda m: spell(m, _attribute_classes(m)[label]), values)
    assert not divergences, f"{label}, {reading}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


class _Probe(NamedTuple):
    """A tuple carrying the two attributes the named tuple rows declare."""

    a: object
    b: object


@pytest.mark.parametrize("hint", ["int", "Annotated[int, ge(0)]"])
def test_a_named_tuple_reads_its_hints_as_vtjson_does(hint: str) -> None:
    """A named tuple's hints keep their `Annotated` metadata."""

    def build(m: Any) -> object:
        fields = [("a", _hints(m)[hint]), ("b", str)]
        return NamedTuple("_Pair", fields)  # ty: ignore[invalid-named-tuple]

    values: list[object] = [_Probe(1, "y"), _Probe(-1, "y"), _Probe("x", "y"), (1,)]
    divergences = _divergences(build, values)
    assert not divergences, f"a: {hint}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
