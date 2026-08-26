"""A subscripted generic is a schema whatever its origin is.

vtjson reads `X[...]` by asking what `X` is: a `Mapping` subclass gives a
mapping over the two arguments, any other `Container` subclass gives a
collection over the one, and the value must additionally be an instance of `X`
itself. Nothing in that rule is restricted to the builtins, so
`Sequence[int]`, `Mapping[str, int]` and `deque[int]` are ordinary schemas.

valgebra builds its container nodes from the builtins, so an origin outside them
has no node to become. Handing the form over whole makes valgebra refuse it, and
a refusal is not a verdict: the layer raised where vtjson decides.

The shape is decided by the equivalent builtin over a converted value and the
origin by an atom beside it — the treatment §22 gave a container schema written
in a foreign class, applied to the class a generic names rather than the one a
literal is written in.
"""

from __future__ import annotations

from collections import (
    Counter,
    OrderedDict,
    UserDict,
    UserList,
    abc,
    defaultdict,
    deque,
)
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


# One value per container implementation a generic can be asked about, plus the
# scalars that belong to none of them.
VALUES: list[object] = [
    {"a": 1},
    {"a": "x"},
    {},
    OrderedDict(a=1),
    defaultdict(None, {"a": 1}),
    Counter(a=1),
    UserDict(a=1),
    [1],
    ["a"],
    [],
    (1,),
    {1},
    {"x"},
    frozenset({1}),
    deque([1]),
    UserList([1]),
    "ab",
    0,
    int,
    None,
]

# Every origin vtjson dispatches on, named by the kind it dispatches to.
ROWS: list[tuple[str, object]] = [
    # A `Mapping` subclass: two arguments, and the value must be one too.
    ("Mapping[str, int]", abc.Mapping[str, int]),
    ("MutableMapping[str, int]", abc.MutableMapping[str, int]),
    ("OrderedDict[str, int]", OrderedDict[str, int]),
    ("defaultdict[str, int]", defaultdict[str, int]),
    ("UserDict[str, int]", UserDict[str, int]),
    # Any other `Container` subclass: one argument, matched against every
    # element the value yields when iterated.
    ("Sequence[int]", abc.Sequence[int]),
    ("MutableSequence[int]", abc.MutableSequence[int]),
    ("Collection[int]", abc.Collection[int]),
    ("Container[int]", abc.Container[int]),
    ("Set[int]", abc.Set[int]),
    ("MutableSet[int]", abc.MutableSet[int]),
    ("deque[int]", deque[int]),
    ("UserList[int]", UserList[int]),
    # An origin that is neither is left to the rule vtjson applies to anything
    # else it cannot place: an instance check if the form answers to `type`, a
    # call otherwise. Which of the two `type[int]` gets depends on the
    # interpreter, so its verdict flips between 3.10 and 3.11 in vtjson too.
    ("Iterable[int]", abc.Iterable[int]),
    ("type[int]", type[int]),
]


@pytest.mark.parametrize(("label", "schema"), ROWS, ids=[r[0] for r in ROWS])
def test_a_generic_over_a_foreign_origin_decides_as_vtjson_does(
    label: str,
    schema: object,
) -> None:
    """Every value reaches the same verdict under both libraries."""
    divergences = [
        (obj, a, b)
        for obj in VALUES
        if (a := _decide(vt, schema, obj)) != (b := _decide(vg, schema, obj))
    ]
    assert not divergences, f"{label}: " + ", ".join(
        f"{obj!r} vtjson={a} layer={b}" for obj, a, b in divergences
    )


# A generic carries a fixed number of arguments for the kind its origin picks,
# and the wrong number is a schema that cannot be built.
# The arities are wrong on purpose, which is what a type checker objects to.
ARITIES: list[tuple[str, Callable[[], object], str]] = [
    ("Counter[str]", lambda: Counter[str], "mapping"),
    ("Mapping[str]", lambda: abc.Mapping[str], "mapping"),  # ty: ignore[invalid-type-arguments]
    ("Sequence[int, str]", lambda: abc.Sequence[int, str], "Generic"),  # ty: ignore[invalid-type-arguments]
]


@pytest.mark.parametrize(
    ("label", "build", "expected"), ARITIES, ids=[a[0] for a in ARITIES]
)
def test_the_wrong_number_of_arguments_is_a_schema_error(
    label: str,
    build: Callable[[], object],
    expected: str,
) -> None:
    """Both libraries refuse to build it, and neither reports it as a verdict."""
    try:
        schema = build()
    except TypeError:
        pytest.skip(f"{label} cannot be spelled on this interpreter")

    with pytest.raises(vt.SchemaError) as reference:
        vt.validate(schema, {})
    with pytest.raises(vg.SchemaError) as layer:
        vg.validate(schema, {})

    assert expected in str(reference.value)
    assert str(layer.value) == str(reference.value)
