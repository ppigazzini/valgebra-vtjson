"""A schema `validate` and `safe_cast` translated is kept, and read again once changed.

vtjson compiles the schema on every call, so a schema a caller changes in place
between two calls is read as it stands at each. The layer keeps a translation for
the schema it was made from, and these hold that a change in place, wherever it
sits, is read again, as vtjson reads it, and that a schema nothing changed is not
translated twice.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

import pytest
import vtjson as vt

import vtjson_compat as vg
from vtjson_compat import _translate as translation

if TYPE_CHECKING:
    from collections.abc import Callable


def _accepts(library: Any, schema: object, obj: object) -> bool:
    try:
        library.validate(schema, obj)
    except (vt.ValidationError, vg.ValidationError):
        return False
    return True


def _cast(schema: object, obj: object) -> bool:
    try:
        vg.safe_cast(schema, obj)
    except vg.ValidationError:
        return False
    return True


# Each row: a schema built by one library, a value, and a change made in place
# that moves the value's verdict.
_CHANGES: list[tuple[str, Callable[[Any], object], object, Callable[[Any], None]]] = [
    (
        "a field's schema replaced",
        lambda _m: {"a": int},
        {"a": 1},
        lambda schema: schema.__setitem__("a", str),
    ),
    (
        "a key added",
        lambda _m: {"a": int},
        {"a": 1},
        lambda schema: schema.__setitem__("b", int),
    ),
    (
        "a record inside a list",
        lambda _m: [{"a": int}, ...],
        [{"a": 1}],
        lambda schema: schema[0].__setitem__("a", str),
    ),
    (
        "a list's item",
        lambda _m: [int, ...],
        [1],
        lambda schema: schema.__setitem__(0, str),
    ),
    (
        "a record inside lax",
        lambda m: {"lax": m.lax(fields := {"a": int}), "fields": fields},
        {"a": 1},
        lambda held: held["fields"].__setitem__("a", str),
    ),
    (
        "a record inside intersect",
        lambda m: {"both": m.intersect(fields := {"a": int}, dict), "fields": fields},
        {"a": 1},
        lambda held: held["fields"].__setitem__("a", str),
    ),
]


def _schema(built: object) -> object:
    """Return the schema a row validates against: a construct's, where it holds one."""
    if isinstance(built, dict) and ("lax" in built or "both" in built):
        return built.get("lax", built.get("both"))
    return built


@pytest.mark.parametrize(
    ("build", "obj", "change"),
    [row[1:] for row in _CHANGES],
    ids=[row[0] for row in _CHANGES],
)
def test_a_schema_changed_in_place_is_read_again(
    build: Callable[[Any], object], obj: object, change: Callable[[Any], None]
) -> None:
    """Each engine reads the schema as it stands at each call, before and after."""
    held = {"vtjson": build(vt), "layer": build(vg)}
    before = (
        _accepts(vt, _schema(held["vtjson"]), obj),
        _accepts(vg, _schema(held["layer"]), obj),
    )
    assert before == (True, True)
    assert _cast(_schema(held["layer"]), obj)
    change(held["vtjson"])
    change(held["layer"])
    after = (
        _accepts(vt, _schema(held["vtjson"]), obj),
        _accepts(vg, _schema(held["layer"]), obj),
    )
    assert after == (False, False)
    assert not _cast(_schema(held["layer"]), obj)


def test_a_schema_nothing_changed_is_translated_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second call on the same schema translates nothing."""
    calls = []
    original = translation._translate  # noqa: SLF001

    def counted(schema: object, **how: Any) -> object:
        calls.append(schema)
        return original(schema, **how)

    monkeypatch.setattr(translation, "_translate", counted)
    schema = {"a": int, "b": [str, ...]}
    vg.validate(schema, {"a": 1, "b": ["x"]})
    first = len(calls)
    vg.validate(schema, {"a": 2, "b": []})
    vg.safe_cast(schema, {"a": 3, "b": ["y"]})
    assert first > 0
    assert len(calls) == first


def _alternating(library: Any) -> object:
    """Return a caller's wrapper reading another schema at each `__compile__`."""

    class Alternating(library.wrapper):
        def __init__(self) -> None:
            self.calls = 0

        def __compile__(self, _deferred_compiles: object = None) -> object:
            self.calls += 1
            return library.compile(int if self.calls % 2 else str)

    return Alternating()


@pytest.mark.parametrize("library", [vt, vg], ids=["vtjson", "layer"])
def test_a_callers_wrapper_is_compiled_on_every_call(library: Any) -> None:
    """Each engine asks a wrapper's `__compile__` on every call."""
    schema = _alternating(library)
    assert [_accepts(library, schema, 1), _accepts(library, schema, 1)] == [True, False]


def test_the_table_keeps_at_most_its_bound() -> None:
    """Fresh schemas, one a call, keep no more translations than the bound."""
    bound = translation._KEPT  # noqa: SLF001
    for width in range(2 * bound):
        vg.validate({f"k{width}": int}, {f"k{width}": 1})
    assert len(translation._TRANSLATED) <= bound  # noqa: SLF001


def test_threads_share_the_table() -> None:
    """Threads validating one schema and fresh ones at once each read their own."""
    shared = {"a": int}
    failures: list[BaseException] = []

    def work(offset: int) -> None:
        try:
            for step in range(200):
                assert _accepts(vg, shared, {"a": step})
                fresh = {f"k{offset}-{step}": str}
                assert _accepts(vg, fresh, {f"k{offset}-{step}": "x"})
                assert not _accepts(vg, fresh, {f"k{offset}-{step}": 1})
        except BaseException as exc:  # noqa: BLE001  (reported by the main thread)
            failures.append(exc)

    threads = [threading.Thread(target=work, args=(offset,)) for offset in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not failures
    assert len(translation._TRANSLATED) <= translation._KEPT  # noqa: SLF001
