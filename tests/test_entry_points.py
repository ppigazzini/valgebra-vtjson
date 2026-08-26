"""The four public ways to ask the same question agree with each other.

`validate` translates per call, `compile` translates once and keeps the
validator, `make_type` hands back a class whose `isinstance` is the schema, and
`safe_cast` checks and returns the value. Each is a different path through the
translator, and the differential suite runs only the first.

They are also where a mode is chosen. `validate` takes `strict`, `make_type`
takes its own, and `compile` takes neither — so an entry point is a place a
schema's strictness can be settled differently from the way it was written.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple, TypedDict

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable


class _Row(TypedDict):
    a: int


class _Pt(NamedTuple):
    a: int


def _by_validate(module: Any, schema: object, obj: object) -> str:
    """Translate per call, as vtjson's own ``validate`` does."""
    try:
        module.validate(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


def _by_compile(module: Any, schema: object, obj: object) -> str:
    """Translate once, then ask the compiled schema."""
    compiled = module.compile(schema)
    try:
        module.validate(compiled, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


def _by_make_type(module: Any, schema: object, obj: object) -> str:
    """Ask the class the schema is turned into."""
    return "accept" if isinstance(obj, module.make_type(schema, "T")) else "reject"


def _by_safe_cast(module: Any, schema: object, obj: object) -> str:
    """Check the value and hand it back."""
    try:
        module.safe_cast(schema, obj)
    except module.ValidationError:
        return "reject"
    return "accept"


ENTRIES: list[tuple[str, Callable[[Any, object, object], str]]] = [
    ("validate", _by_validate),
    ("compile", _by_compile),
    ("make_type", _by_make_type),
    ("safe_cast", _by_safe_cast),
]

SCHEMAS: list[tuple[str, Callable[[Any], object]]] = [
    ("a record", lambda m: {"a": int}),  # noqa: ARG005
    ("a catch-all", lambda m: {"a": int, str: int}),  # noqa: ARG005
    ("an optional key", lambda m: {"a?": int}),  # noqa: ARG005
    ("a repeated list", lambda m: [int, ...]),  # noqa: ARG005
    ("a TypedDict", lambda m: _Row),  # noqa: ARG005
    ("a NamedTuple", lambda m: _Pt),  # noqa: ARG005
    ("a union", lambda m: m.union({"a": int}, str)),
    ("a lax record", lambda m: m.lax({"a": int})),
    ("a strict record", lambda m: m.strict({"a": int})),
    ("a refinement", lambda m: m.ge(0)),
]

VALUES: list[object] = [
    {"a": 1},
    {"a": "x"},
    {"a": 1, "z": 2},
    {},
    [1],
    [1, "x"],
    "s",
    1,
    -1,
    _Pt(1),
    None,
]


@pytest.mark.parametrize(("entry", "ask"), ENTRIES, ids=[e[0] for e in ENTRIES])
@pytest.mark.parametrize(("label", "build"), SCHEMAS, ids=[s[0] for s in SCHEMAS])
def test_every_entry_point_reaches_vtjson_s_verdict(
    entry: str,
    ask: Callable[[Any, object, object], str],
    label: str,
    build: Callable[[Any], object],
) -> None:
    """The path taken to the translator does not change the answer."""
    divergences = [
        (obj, a, b)
        for obj in VALUES
        if (a := ask(vt, build(vt), obj)) != (b := ask(vg, build(vg), obj))
    ]
    assert not divergences, f"{label} via {entry}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


@pytest.mark.parametrize("strict", [True, False], ids=["strict", "lax"])
def test_the_mode_an_entry_point_takes_reaches_the_same_record(
    strict: bool,  # noqa: FBT001
) -> None:
    """`validate` and `make_type` both carry a mode, and carry the same one."""
    schema = {"a": int}
    probes: list[object] = [{"a": 1}, {"a": 1, "z": 2}, {"a": "x"}]
    for obj in probes:
        try:
            vt.validate(schema, obj, strict=strict)
            reference = "accept"
        except vt.ValidationError:
            reference = "reject"

        try:
            vg.validate(schema, obj, strict=strict)
            through_validate = "accept"
        except vg.ValidationError:
            through_validate = "reject"

        as_type = vg.make_type(schema, "T", strict=strict)
        through_type = "accept" if isinstance(obj, as_type) else "reject"

        assert through_validate == reference, f"validate: {obj!r}"
        assert through_type == reference, f"make_type: {obj!r}"
