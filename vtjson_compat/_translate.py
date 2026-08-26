"""The vtjson-to-valgebra translator and its shared helpers.

``_translate`` turns a vtjson-style schema spec into a valgebra validator. It is
a translator, not a passthrough: several vtjson implicit forms differ from
valgebra's native frontend (lists, ``float``), and where vtjson is lax the lax
meaning is expressed with the algebra so the accept/reject decision matches.
"""

import importlib
import math
from collections.abc import Callable
from collections.abc import Set as AbstractSet
from typing import Annotated

from ._valgebra_api import CompiledValidator
from ._valgebra_api import (
    anything as _anything,
)
from ._valgebra_api import (
    complement as _complement,
)
from ._valgebra_api import (
    fixed_sequence as _fixed_sequence,
)
from ._valgebra_api import (
    intersect as _intersect,
)
from ._valgebra_api import (
    union as _union,
)
from ._valgebra_api import (
    validator as _validator,
)

# The builtin `dict`, captured before `protocol`'s `dict=` parameter shadows it.
_DICT = dict


class SchemaError(Exception):
    """A schema's own arguments are malformed, so it denotes no set of values.

    Distinct from ``ValidationError``, which reports a value outside a
    well-formed schema. The separation is what lets a caller tell a bad document
    from a bad schema: a bound that cannot be compared against, or a pattern that
    cannot be compiled, would otherwise become a validator with a constant
    verdict and no explanation.
    """


def _bound(value: object, role: str) -> object:
    """Return a comparison bound, refusing one nothing can be ordered against.

    A bound valgebra cannot read contributes no constraint, so the refinement
    widens to every value rather than narrowing. Self-comparison is the probe:
    it needs no second operand and no assumption about what will be validated.
    """
    try:
        # Whether the operator exists at all is the question being asked, so
        # the checker cannot be expected to know that it does.
        _ = value <= value  # noqa: PLR0124  # ty: ignore[unsupported-operator]
    except TypeError as exc:
        msg = f"the {role} bound {value!r} does not support comparison"
        raise SchemaError(msg) from exc
    return value


def _integer(value: object, role: str) -> int:
    """Return ``value`` as an integer, or refuse the schema."""
    if not isinstance(value, int):
        msg = f"the {role} {value!r} is not an integer"
        raise SchemaError(msg)
    return value


def _text(value: object, role: str) -> str:
    """Return ``value`` as a string, or refuse the schema."""
    if not isinstance(value, str):
        msg = f"the {role} {value!r} is not a string"
        raise SchemaError(msg)
    return value


def _number(value: object, role: str) -> int | float:
    """Return ``value`` as a real number, or refuse the schema."""
    if not isinstance(value, int | float):
        msg = f"the {role} {value!r} is not a number"
        raise SchemaError(msg)
    return value


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


def _require(module: str, extra: str) -> object:
    """Import an optional dependency, naming the extra that installs it.

    The extra is the caller's to state: the constructs are split across more
    than one, so a single hard-coded name sends half of them somewhere that
    does not provide what they need.
    """
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        msg = (
            f"the '{module}' package is required for this vtjson construct; "
            f"install it with: pip install valgebra-vtjson[{extra}]"
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


def _near(value: float) -> CompiledValidator:
    """Build the set a bare float constant denotes: the floats close to ``value``.

    vtjson reads a float schema as a tolerance rather than an identity, so
    ``1.5`` admits any float within ``math.isclose``'s default relative
    tolerance of it. The type test is what keeps the layer's documented reading
    of a constant as a *typed* singleton: an ``int`` equal to the bound is a
    separate, ledgered divergence and is not widened here.
    """

    def check(obj: object) -> bool:
        return type(obj) is float and math.isclose(obj, value)

    return _predicate(check)


def _translate(  # noqa: PLR0911
    schema: object, *, exact: bool = False, open_records: bool = False
) -> CompiledValidator:
    """Translate a vtjson-style schema spec into a valgebra validator.

    With ``exact``, a float constant is matched by equality rather than by
    tolerance. Dict keys are looked up, not compared, so vtjson matches a float
    key exactly even though it matches a float *value* approximately.

    With ``open_records``, every dict in the subtree admits a key no clause of
    its own claims — vtjson's lax mode. A validator already built is returned
    unchanged, so a wrapper cannot reach inside one and the innermost mode
    stands, as it does in vtjson.
    """
    if isinstance(schema, CompiledValidator):
        return schema
    if schema is None:
        return _validator(None)
    if isinstance(schema, type):
        return _translate_type(schema, open_records=open_records)
    if isinstance(schema, dict):
        return _translate_dict(schema, open_records=open_records)
    if isinstance(schema, list):
        return _translate_list(schema, open_records=open_records)
    if isinstance(schema, tuple):
        return _translate_tuple(schema, open_records=open_records)
    if isinstance(schema, AbstractSet):
        return _translate_set(schema, open_records=open_records)
    return _translate_leaf(schema, exact=exact)


def _translate_leaf(schema: object, *, exact: bool) -> CompiledValidator:
    """Translate a schema that is not a container: a predicate or a constant."""
    if callable(schema):
        if getattr(schema, "_vtjson_nullary", False):
            # A bare nullary construct, like vtjson's auto-instantiated bare class.
            return _translate(schema())  # ty: ignore[call-top-callable]
        # A bare callable is a predicate over any value (the vtjson convention).
        return _validator(Annotated[object, schema])
    if isinstance(schema, float) and not exact:
        return _near(schema)
    # Anything else is an exact-value constant matched by equality.
    return _validator(schema)


def _translate_type(schema: type, *, open_records: bool = False) -> CompiledValidator:
    builder = _SCALAR.get(schema)
    if builder is not None:
        return builder()
    if schema is type(None):
        return _validator(None)
    # Any other class translates directly: valgebra reads dataclasses, NamedTuples,
    # Enums, TypedDicts, and runtime Protocols structurally, and a bare class as an
    # instance check — the isinstance semantics vtjson gives a plain type.
    built = _validator(schema)
    if open_records:
        # A `TypedDict` declares keys, so laxness frees the ones it does not.
        # `open` reaches a record and nothing else, which is the whole rule: an
        # instance check and an attribute schema declare no key to free, and a
        # declared field keeps deciding because a named field takes precedence
        # over the clause opening adds.
        return built.open()
    return built


# The plain builtins carry no demand beyond their kind. Any other class a
# container schema is written in narrows the contract to that class.
_PLAIN = (dict, list, tuple, set)


def _of_own_class(schema: object, structure: CompiledValidator) -> CompiledValidator:
    """Narrow ``structure`` to the class ``schema`` is written in.

    vtjson reads a container schema for its shape and then requires the value to
    be an instance of the literal's own type, so an ``OrderedDict`` schema admits
    no plain ``dict``. A `frozenset` schema is uninhabited under that rule, since
    the set shape wants a ``set`` and the class wants a ``frozenset``.
    """
    kind = type(schema)
    if kind in _PLAIN:
        return structure
    return _intersect(structure, _validator(kind))


def _translate_list(
    schema: list[object], *, open_records: bool = False
) -> CompiledValidator:
    # vtjson: a trailing `...` repeats the element just before it, so `[T, ...]`
    # is a homogeneous list and `[A, ..., Z, ...]` is a fixed prefix then the last
    # element repeated; `[A, B, C]` is a fixed-length positional list; `[]`
    # matches only the empty list. valgebra's native list form expresses each.
    if schema and schema[-1] is Ellipsis:
        # Every position is declared by the repeat, so laxness has nothing to free.
        prefix = [_translate(item, open_records=open_records) for item in schema[:-1]]
        return _of_own_class(schema, _validator([*prefix, ...]))
    declared = [_translate(item, open_records=open_records) for item in schema]
    if open_records:
        # A sequence declares positions the way a record declares keys: laxly the
        # ones it does not declare are free, so an unconstrained element repeats
        # after the declared prefix.
        return _of_own_class(
            schema, _validator([*declared, _validator(_anything), ...])
        )
    return _of_own_class(schema, _fixed_sequence(*declared))


def _translate_tuple(
    schema: tuple[object, ...], *, open_records: bool = False
) -> CompiledValidator:
    # vtjson reads a trailing `...` as it does for lists: the element before it
    # repeats after a fixed prefix. valgebra's frontend expresses every tuple
    # shape, so `(T, ...)`, the prefix form `(A, B, ...)`, and the fixed-length
    # `(A, B, C)` all translate. The subscription drives the frontend at runtime,
    # not as a static type.
    if schema and schema[-1] is Ellipsis:
        args = (
            *(_translate(item, open_records=open_records) for item in schema[:-1]),
            Ellipsis,
        )
        return _of_own_class(schema, _validator(tuple[args]))  # ty: ignore[invalid-type-form]
    # valgebra reads a fixed-length tuple as the subscription `tuple[A, B]`, not a
    # tuple literal, so build the generic alias from the translated elements.
    fixed = tuple(_translate(item, open_records=open_records) for item in schema)
    if open_records:
        # As for a list: the positions the tuple does not declare are free.
        free = (*fixed, _validator(_anything), Ellipsis)
        return _of_own_class(schema, _validator(tuple[free]))  # ty: ignore[invalid-type-form]
    return _of_own_class(schema, _validator(tuple[fixed]))  # ty: ignore[invalid-type-form]


def _translate_set(
    schema: AbstractSet[object], *, open_records: bool = False
) -> CompiledValidator:
    # vtjson reads a set schema as "every element matches one of these schemas":
    # a single element is homogeneous, several union, and the empty set `set()`
    # matches only the empty set. valgebra expresses each as a set of the union
    # of the element schemas (an empty union is the uninhabited element type, so
    # `set()` becomes the set whose only member is the empty set).
    element = _union(*(_translate(item, open_records=open_records) for item in schema))
    return _of_own_class(schema, _validator(set[element]))  # ty: ignore[invalid-type-form]


def _translate_dict(
    schema: dict[object, object], *, open_records: bool = False
) -> CompiledValidator:
    if not schema:
        # No clause at all: strictly, only the empty dict has no unclaimed key;
        # laxly, every key is unclaimed and so every dict belongs.
        empty = {_complement(_union()): _validator(_anything)} if open_records else {}
        return _of_own_class(schema, _validator(empty))
    # A string key is a record field (a trailing "?" marks it optional); any
    # other key is a schema constraining the rest. valgebra's native dict form
    # combines both — named fields plus one or more key-pattern catch-all clauses
    # — so records, single mappings, multi-clause maps, and a record mixed with a
    # catch-all all translate uniformly.
    catch_alls = {
        key: (
            _translate(key, exact=True),
            _translate(value, open_records=open_records),
        )
        for key, value in schema.items()
        if not isinstance(key, str)
    }
    translated: dict[object, CompiledValidator] = {}
    for key, value in schema.items():
        if not isinstance(key, str):
            pattern, clause = catch_alls[key]
            translated[pattern] = clause
            continue
        # vtjson admits a key when *any* clause claiming it admits the value, so
        # a field its own catch-alls also claim has more than one way to pass.
        # Which catch-alls claim a literal key is settled here, not per value.
        field = _translate(value, open_records=open_records)
        alternatives = [
            clause
            for pattern, clause in catch_alls.values()
            if pattern.is_valid(_field_name(key))
        ]
        translated[key] = _union(field, *alternatives) if alternatives else field
    if open_records:
        translated[_unclaimed_key(schema, catch_alls)] = _validator(_anything)
    return _of_own_class(schema, _validator(translated))


def _unclaimed_key(
    schema: dict[object, object],
    catch_alls: dict[object, tuple[CompiledValidator, CompiledValidator]],
) -> CompiledValidator:
    """Build the key schema for the keys no clause of ``schema`` claims.

    Laxness excuses a key **no** clause matches, so the permissive clause is the
    complement of the ones that do. Giving it every key instead — which is what
    opening a compiled record does — would subsume the narrower clauses and free
    the keys the schema was written to constrain.
    """
    claimed = [
        _validator(_field_name(key)) for key in schema if isinstance(key, str)
    ] + [pattern for pattern, _ in catch_alls.values()]
    return _complement(_union(*claimed))


def _field_name(key: str) -> str:
    """Return the field a record key declares, without the optional mark."""
    return key.removesuffix("?")
