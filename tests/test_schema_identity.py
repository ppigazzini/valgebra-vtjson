"""Translation keys state on a schema's identity, so identity is an axis.

Finding a cycle means recognising a container the descent is already inside, and
that recognition is by `id`. Two things follow, and neither is checked anywhere
else: a schema object written in several places is not a cycle and must not be
read as one, and the state that records the descent belongs to one thread.

The constructs add a second reason. A construct holds its arguments untranslated
until a mode is known, and answers as a validator by building one on first use —
so the moment that build happens is a moment the translator is re-entered.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

import pytest
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


def _shared(module: Any) -> object:
    """Return a schema holding one record object in two places."""
    record = {"a": int}
    return {"x": record, "y": record}


def _shared_one_strict(module: Any) -> object:
    """Return the same, with one of the two positions settled strictly."""
    record = {"a": int}
    return {"x": record, "y": module.strict(record)}


def _shared_in_a_list(module: Any) -> object:
    """Return a list holding one record object twice."""
    record = {"a": int}
    return [record, record]


def _shared_recursive(module: Any) -> object:
    """Return a schema holding one *recursive* record in two places."""
    node: dict[object, object] = {}
    node.update({"v": int, "kids": [node, ...]})
    return {"l": node, "r": node}


def _built_before_use(module: Any) -> object:
    """Return a record whose construct was forced to build before translation.

    A construct answers as a validator by building one, and doing that first is
    what makes the enclosing translation meet an already-built argument.
    """
    construct = module.union({"a": int}, str)
    _ = repr(construct)
    return {"x": construct}


SHARED: list[tuple[str, Callable[[Any], object], list[object]]] = [
    (
        "one record in two fields",
        _shared,
        [
            {"x": {"a": 1}, "y": {"a": 1}},
            {"x": {"a": 1}, "y": {"a": "z"}},
            {"x": {"a": 1, "e": 2}, "y": {"a": 1}},
        ],
    ),
    (
        "one record, one position strict",
        _shared_one_strict,
        [{"x": {"a": 1}, "y": {"a": 1}}, {"x": {"a": 1}, "y": {"a": 1, "e": 2}}],
    ),
    (
        "one record twice in a list",
        _shared_in_a_list,
        [[{"a": 1}, {"a": 1}], [{"a": 1}, {"a": "z"}]],
    ),
    (
        "one recursive record in two fields",
        _shared_recursive,
        [
            {"l": {"v": 1, "kids": []}, "r": {"v": 2, "kids": []}},
            {"l": {"v": 1, "kids": [{"v": 3, "kids": []}]}, "r": {"v": 2, "kids": []}},
            {"l": {"v": "x", "kids": []}, "r": {"v": 2, "kids": []}},
        ],
    ),
    (
        "a construct built before translation",
        _built_before_use,
        [{"x": {"a": 1}}, {"x": "s"}, {"x": {"a": 1, "e": 2}}],
    ),
]


@pytest.mark.parametrize(
    ("label", "build", "objects"), SHARED, ids=[s[0] for s in SHARED]
)
def test_a_schema_written_twice_is_not_a_cycle(
    label: str,
    build: Callable[[Any], object],
    objects: list[object],
) -> None:
    """Reuse and self-reference are different things, told apart by nesting."""
    reference, layer = build(vt), build(vg)
    divergences = [
        (obj, a, b)
        for obj in objects
        if (a := _decide(vt, reference, obj)) != (b := _decide(vg, layer, obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


def test_the_same_shapes_translate_correctly_on_many_threads() -> None:
    """The descent's state is per thread, so threads do not share a path."""
    workers = 16
    outcomes: list[str] = ["not started"] * workers

    def run(index: int) -> None:
        try:
            node: dict[object, object] = {}
            node.update({"v": int, "kids": [node, ...]})
            vg.validate(node, {"v": 1, "kids": [{"v": 2, "kids": []}]})

            record = {"a": int}
            vg.validate({"x": record, "y": record}, {"x": {"a": 1}, "y": {"a": 1}})
            vg.validate(vg.lax(record), {"a": 1, "z": 2})
            outcomes[index] = "ok"
        except Exception as exc:  # noqa: BLE001  (the report is the assertion)
            outcomes[index] = f"{type(exc).__name__}: {exc}"

    threads = [threading.Thread(target=run, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert set(outcomes) == {"ok"}, f"threads reported {sorted(set(outcomes))}"
