r"""How a key says whether it is required, wherever a key is read.

vtjson reads a string key through `_canonize_key`: a trailing `?` marks the key
optional and is dropped, and a `\?` ending a key longer than two characters is a
literal `?` ending a required one. `optional_key(key, _optional)` says the same
for any key, its text taken as written, so a string ending in `?` can be
required, and a key of another type can be optional. Every key is then one of
two kinds: a constant, which the mapping must carry unless the key is optional,
or a schema, a clause over the keys it matches, which no mark reaches.

The axis is the key's spelling, crossed with each reading that takes one: a dict
schema, the same under `lax`, and `fields`, which reads an object's attributes.
vtjson reads an optional attribute the value lacks anyway, and `getattr` raises
out of `validate`; the layer rejects the value, the direction the ledger
allows, and the rows count that as agreement.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable


def _outcome(module: Any, build: Callable[[], object], obj: object) -> str:
    """Return ``module``'s verdict, that it refused the schema, or that it raised."""
    try:
        module.validate(build(), obj)
    except module.SchemaError:
        return "SchemaError"
    except module.ValidationError:
        return "reject"
    except Exception:  # noqa: BLE001  (vtjson lets a value's exception out)
        return "raise"
    return "accept"


def _agree(reference: str, layer: str) -> bool:
    """Whether the layer reaches vtjson's verdict, or rejects where it raised."""
    return reference == layer or (reference == "raise" and layer == "reject")


# Each spelling of a key, built in a library ``m``.
KEYS: list[tuple[str, Callable[[Any], object]]] = [
    ("a", lambda _m: "a"),
    ("a?", lambda _m: "a?"),
    ("a??", lambda _m: "a??"),
    ("a\\?", lambda _m: "a\\?"),
    ("a\\??", lambda _m: "a\\??"),
    ("a\\", lambda _m: "a\\"),
    ("?", lambda _m: "?"),
    ("\\?", lambda _m: "\\?"),
    ("optional_key('a')", lambda m: m.optional_key("a")),
    ("required optional_key('a')", lambda m: m.optional_key("a", _optional=False)),
    ("optional_key('a?')", lambda m: m.optional_key("a?")),
    ("required optional_key('a?')", lambda m: m.optional_key("a?", _optional=False)),
    ("optional_key(1)", lambda m: m.optional_key(1)),
    ("required optional_key(1)", lambda m: m.optional_key(1, _optional=False)),
    ("optional_key(int)", lambda m: m.optional_key(int)),
]

# Each name a key can spell, so a probe can carry exactly one of them.
NAMES = ["a", "a?", "a??", "a\\", "a\\?", "?", "\\", "", "\\?"]

ITEMS: list[object] = [
    {},
    *({name: 1} for name in NAMES),
    {"a": "x"},
    {"a?": "x"},
    {1: 1},
    {1: "x"},
    {2: 1},
]

ATTRIBUTES: list[object] = [
    SimpleNamespace(),
    *(SimpleNamespace(**{name: 1}) for name in NAMES),
    SimpleNamespace(a="x"),
]

# Each reading of a key, and the values it is asked about.
READINGS: list[tuple[str, Callable[[Any, object], object], list[object]]] = [
    ("a dict", lambda _m, key: {key: int}, ITEMS),
    ("a lax dict", lambda m, key: m.lax({key: int}), ITEMS),
    ("a dict beside a field", lambda _m, key: {key: int, "b?": str}, ITEMS),
    ("fields", lambda m, key: m.fields({key: int}), ATTRIBUTES),
]


@pytest.mark.parametrize(
    ("reading", "spell", "values"), READINGS, ids=[r[0] for r in READINGS]
)
@pytest.mark.parametrize(("label", "key"), KEYS, ids=[k[0] for k in KEYS])
def test_a_key_is_required_as_vtjson_reads_its_spelling(
    label: str,
    key: Callable[[Any], object],
    reading: str,
    spell: Callable[[Any, object], object],
    values: list[object],
) -> None:
    """Each value reaches vtjson's verdict, or a rejection where vtjson raised."""
    divergences = [
        (obj, a, b)
        for obj in values
        if not _agree(
            a := _outcome(vt, lambda: spell(vt, key(vt)), obj),
            b := _outcome(vg, lambda: spell(vg, key(vg)), obj),
        )
    ]
    assert not divergences, f"{label} in {reading}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )
