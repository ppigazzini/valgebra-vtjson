"""The vtjson-to-valgebra translator and its shared helpers.

``_translate`` turns a vtjson-style schema spec into a valgebra validator. It is
a translator, not a passthrough: several vtjson implicit forms differ from
valgebra's native frontend (lists, ``float``), and where vtjson is lax the lax
meaning is expressed with the algebra so the accept/reject decision matches.
"""

import importlib
from collections.abc import Callable
from typing import Annotated

from ._valgebra_api import CompiledValidator
from ._valgebra_api import (
    fixed_sequence as _fixed_sequence,
)
from ._valgebra_api import (
    union as _union,
)
from ._valgebra_api import (
    validator as _validator,
)

# The builtin `dict`, captured before `protocol`'s `dict=` parameter shadows it.
_DICT = dict


class _Marker:
    """A structural refinement marker.

    valgebra's frontend reads annotated-types-style markers by attribute
    (``ge``/``gt``/``le``/``lt``/``min_length``/``max_length``), so an instance
    carrying only the relevant attributes contributes exactly those constraints
    without any runtime dependency on ``annotated_types``.
    """

    def __init__(self, **bounds: object) -> None:
        self.__dict__.update(bounds)


def _refine(marker: _Marker) -> CompiledValidator:
    """Build a validator for ``object`` narrowed by one refinement marker."""
    return _validator(Annotated[object, marker])


def _predicate(check: object) -> CompiledValidator:
    """Build a validator that admits a value iff ``check(value)`` is truthy."""
    return _validator(Annotated[object, check])


def _nullary(
    func: Callable[..., CompiledValidator],
) -> Callable[..., CompiledValidator]:
    """Tag a construct factory vtjson also accepts bare, without a call.

    vtjson auto-instantiates a bare construct *class* used as a schema (e.g.
    ``{ip_address: int}`` keys by IP without writing ``ip_address()``). The
    compatibility constructs are factory functions, so a bare one would otherwise
    fall into the predicate branch and be called *on the value*; this tag tells
    ``_translate`` to instantiate it instead, matching vtjson.
    """
    func.__dict__["_vtjson_nullary"] = True
    return func


def _require(module: str) -> object:
    """Import an optional dependency, with a clear hint when it is missing."""
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        msg = (
            f"the '{module}' package is required for this vtjson construct; "
            "install it with: pip install valgebra-vtjson[formats]"
        )
        raise ImportError(msg) from exc


# Scalar types mapped to their valgebra validators. `float` follows vtjson and
# also admits ints; `float_` is the floats-only set (valgebra's own `float`).
_SCALAR = {
    bool: lambda: _validator(bool),
    int: lambda: _validator(int),
    str: lambda: _validator(str),
    bytes: lambda: _validator(bytes),
    float: lambda: _union(_validator(int), _validator(float)),
}


def _translate(schema: object) -> CompiledValidator:  # noqa: PLR0911
    """Translate a vtjson-style schema spec into a valgebra validator."""
    if isinstance(schema, CompiledValidator):
        return schema
    if schema is None:
        return _validator(None)
    if isinstance(schema, type):
        return _translate_type(schema)
    if isinstance(schema, dict):
        return _translate_dict(schema)
    if isinstance(schema, list):
        return _translate_list(schema)
    if isinstance(schema, tuple):
        return _translate_tuple(schema)
    if isinstance(schema, set):
        return _translate_set(schema)
    if callable(schema):
        if getattr(schema, "_vtjson_nullary", False):
            # A bare nullary construct, like vtjson's auto-instantiated bare class.
            return _translate(schema())  # ty: ignore[call-top-callable]
        # A bare callable is a predicate over any value (the vtjson convention).
        return _validator(Annotated[object, schema])
    # Anything else is an exact-value constant matched by equality.
    return _validator(schema)


def _translate_type(schema: type) -> CompiledValidator:
    builder = _SCALAR.get(schema)
    if builder is not None:
        return builder()
    if schema is type(None):
        return _validator(None)
    # Any other class translates directly: valgebra reads dataclasses, NamedTuples,
    # Enums, TypedDicts, and runtime Protocols structurally, and a bare class as an
    # instance check — the isinstance semantics vtjson gives a plain type.
    return _validator(schema)


def _translate_list(schema: list) -> CompiledValidator:
    # vtjson: a trailing `...` repeats the element just before it, so `[T, ...]`
    # is a homogeneous list and `[A, ..., Z, ...]` is a fixed prefix then the last
    # element repeated; `[A, B, C]` is a fixed-length positional list; `[]`
    # matches only the empty list. valgebra's native list form expresses each.
    if schema and schema[-1] is Ellipsis:
        prefix = [_translate(item) for item in schema[:-1]]
        return _validator([*prefix, ...])
    return _fixed_sequence(*(_translate(item) for item in schema))


def _translate_tuple(schema: tuple) -> CompiledValidator:
    # vtjson reads a trailing `...` as it does for lists: the element before it
    # repeats after a fixed prefix. valgebra's frontend expresses every tuple
    # shape, so `(T, ...)`, the prefix form `(A, B, ...)`, and the fixed-length
    # `(A, B, C)` all translate. The subscription drives the frontend at runtime,
    # not as a static type.
    if schema and schema[-1] is Ellipsis:
        args = (*(_translate(item) for item in schema[:-1]), Ellipsis)
        return _validator(tuple[args])  # ty: ignore[invalid-type-form]
    # valgebra reads a fixed-length tuple as the subscription `tuple[A, B]`, not a
    # tuple literal, so build the generic alias from the translated elements.
    fixed = tuple(_translate(item) for item in schema)
    return _validator(tuple[fixed])  # ty: ignore[invalid-type-form]


def _translate_set(schema: set) -> CompiledValidator:
    # vtjson reads a set schema as "every element matches one of these schemas":
    # a single element is homogeneous, several union, and the empty set `set()`
    # matches only the empty set. valgebra expresses each as a set of the union
    # of the element schemas (an empty union is the uninhabited element type, so
    # `set()` becomes the set whose only member is the empty set).
    element = _union(*(_translate(item) for item in schema))
    return _validator(set[element])  # ty: ignore[invalid-type-form]


def _translate_dict(schema: dict) -> CompiledValidator:
    if not schema:
        return _validator({})
    # A string key is a record field (a trailing "?" marks it optional); any
    # other key is a schema constraining the rest. valgebra's native dict form
    # combines both — named fields plus one or more key-pattern catch-all clauses
    # — so records, single mappings, multi-clause maps, and a record mixed with a
    # catch-all all translate uniformly.
    translated = {
        (key if isinstance(key, str) else _translate(key)): _translate(value)
        for key, value in schema.items()
    }
    return _validator(translated)
