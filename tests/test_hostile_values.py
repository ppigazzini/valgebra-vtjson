"""A value that breaks under inspection is a value that failed, not a bad schema.

Several constructs reach into a value: they call `len`, `in`, `getattr`, `%`, or
a parsing routine. When that call raises, valgebra reports `predicate_error` —
a diagnostic that names the *schema* as the thing at fault. For these
constructs the schema is fine and the value is not, so the report is misleading
in exactly the situation where a reader most needs it to be right.

`unique` is the one case where the verdict itself is wrong rather than the
explanation: vtjson falls back to a comparison that never hashes, so it admits
what the layer rejects.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator


class HostileMapping(Mapping):
    """A mapping whose membership test raises."""

    def __contains__(self, key: object) -> bool:
        msg = "membership raised"
        raise RuntimeError(msg)

    def __getitem__(self, key: object) -> int:
        return 1

    def __iter__(self) -> Iterator[str]:
        return iter(["a"])

    def __len__(self) -> int:
        return 1


class HostileAttribute:
    """An object whose attribute access raises."""

    @property
    def a(self) -> int:
        msg = "attribute raised"
        raise RuntimeError(msg)


class HostileInt(int):
    """An integer whose arithmetic raises."""

    def __mod__(self, other: object) -> int:
        msg = "modulo raised"
        raise RuntimeError(msg)

    def __sub__(self, other: object) -> int:
        msg = "subtraction raised"
        raise RuntimeError(msg)


class Unhashable:
    """A distinct object that cannot be hashed but can be compared."""

    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        msg = "hash raised"
        raise RuntimeError(msg)


def _verdict(schema: object, obj: object) -> tuple[str | None, str]:
    """Return the violation code ``obj`` produces under ``schema``, and its text."""
    try:
        vg.validate(schema, obj)
    except vg.ValidationError as failure:
        return failure.code, str(failure)
    return None, "admitted"


def _unhashable_pair() -> object:
    """Return an iterable of two distinct, unhashable, comparable objects."""
    return [Unhashable(), Unhashable()]


# A label, the schema, and a value whose own dunder raises under it.
HOSTILE: list[tuple[str, Callable[[Any], object], object]] = [
    ("url on a malformed URL", lambda m: m.url(), "http://[::1"),
    (
        "close_to with a negative tolerance",
        lambda m: m.close_to(1.0, rel_tol=-0.1),
        1.0,
    ),
    ("keys on a raising __contains__", lambda m: m.keys("a"), HostileMapping()),
    ("one_of on a raising __contains__", lambda m: m.one_of("a"), HostileMapping()),
    (
        "fields on a raising property",
        lambda m: m.fields({"a": int}),
        HostileAttribute(),
    ),
    ("div on raising arithmetic", lambda m: m.div(3), HostileInt(9)),
]


@pytest.mark.parametrize(
    ("label", "build", "obj"), HOSTILE, ids=[row[0] for row in HOSTILE]
)
def test_a_hostile_value_is_reported_as_a_value(
    label: str,
    build: Callable[[Any], object],
    obj: object,
) -> None:
    """A rejection blames the value, never the predicate that inspected it."""
    code, message = _verdict(build(vg), obj)
    assert code != "predicate_error", (
        f"{label}: rejected with {code!r}, which names the schema as the "
        f"fault — {message}"
    )


def test_unique_admits_unhashable_members_as_vtjson_does() -> None:
    """Hashing is an optimisation, and failing at it is not an answer.

    vtjson tries `len(set(obj))` and, when that raises for any reason, falls
    through to a comparison scan that never hashes. Two distinct objects
    compare unequal, so the iterable is unique under both readings.
    """
    assert vg.compile(vg.unique()).is_valid(_unhashable_pair())

    def accepts(module: Any, schema: object) -> bool:
        try:
            module.validate(schema, _unhashable_pair())
        except module.ValidationError:
            return False
        return True

    assert accepts(vt, vt.unique()) == accepts(vg, vg.unique())
