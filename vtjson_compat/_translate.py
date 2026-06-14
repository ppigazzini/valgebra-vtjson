"""The vtjson-to-valgebra translator and its shared helpers.

``_translate`` turns a vtjson-style schema spec into a valgebra validator. It is
a translator, not a passthrough: several vtjson implicit forms differ from
valgebra's native frontend (lists, ``float``), and where vtjson is lax the lax
meaning is expressed with the algebra so the accept/reject decision matches.
"""

import importlib
from collections.abc import Callable
from typing import Annotated

from valgebra._valgebra import CompiledValidator
from valgebra._valgebra import (
    fixed_sequence as _fixed_sequence,
)
from valgebra._valgebra import (
    union as _union,
)
from valgebra._valgebra import (
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
    try:
        # dataclasses, NamedTuples, Enums, TypedDicts, runtime Protocols.
        return _validator(schema)
    except NotImplementedError:
        # Any other class: an isinstance check, as vtjson does for a bare type.
        return _validator(Annotated[object, lambda value: isinstance(value, schema)])


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
    if len(schema) >= 1 and schema[-1] is Ellipsis:
        if len(schema) != 2:  # noqa: PLR2004
            msg = "only the homogeneous tuple form (T, ...) is supported so far"
            raise NotImplementedError(msg)
        # The typing form builds a variadic tuple; a raw `(T, ...)` tuple would
        # be read as a fixed pair whose second element must equal Ellipsis. The
        # subscription is used at runtime to drive the frontend, not as a type.
        element = _translate(schema[0])
        return _validator(tuple[element, ...])  # ty: ignore[invalid-type-form]
    return _validator(tuple(_translate(item) for item in schema))


def _translate_set(schema: set) -> CompiledValidator:
    if len(schema) != 1:
        msg = "only the single-element set form {T} is supported so far"
        raise NotImplementedError(msg)
    (element,) = schema
    return _validator({_translate(element)})


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
