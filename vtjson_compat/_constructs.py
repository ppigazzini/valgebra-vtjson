"""The vtjson combinators, refinements, modifiers, predicates, and wrappers.

Each mirrors a vtjson construct on top of the valgebra algebra. The dict
modifiers, structural checks, and numeric/sequence predicates are expressed as
predicates over any value (valgebra's documented slow path), so the
accept/reject decision matches vtjson; a predicate returns False on a type it
cannot handle, mirroring vtjson's reject.
"""

import math
from collections.abc import Callable, Mapping
from types import EllipsisType

from ._translate import (
    SchemaError,
    _attributes_match,
    _bound,
    _integer,
    _Marker,
    _nullary,
    _number,
    _predicate,
    _refine,
    _structural,
    _text,
    _translate,
)
from ._valgebra_api import (
    CompiledValidator,
    anything,
)
from ._valgebra_api import (
    complement as _complement,
)
from ._valgebra_api import cond as _derived_cond
from ._valgebra_api import ifthen as _derived_ifthen
from ._valgebra_api import (
    intersect as _intersect,
)
from ._valgebra_api import (
    union as _union,
)
from ._valgebra_api import (
    validator as _validator,
)


def gt(lb: object) -> CompiledValidator:
    """Values strictly greater than ``lb``."""
    return _refine(_Marker(gt=_bound(lb, "lower")))


def ge(lb: object) -> CompiledValidator:
    """Values greater than or equal to ``lb``."""
    return _refine(_Marker(ge=_bound(lb, "lower")))


def lt(ub: object) -> CompiledValidator:
    """Values strictly less than ``ub``."""
    return _refine(_Marker(lt=_bound(ub, "upper")))


def le(ub: object) -> CompiledValidator:
    """Values less than or equal to ``ub``."""
    return _refine(_Marker(le=_bound(ub, "upper")))


def interval(
    lb: object,
    ub: object,
    strict_lb: bool = False,  # noqa: FBT001, FBT002
    strict_ub: bool = False,  # noqa: FBT001, FBT002
) -> CompiledValidator:
    """Values in the interval between ``lb`` and ``ub``.

    Following vtjson, ``...`` on either end means that end is unbounded, so the
    bound is omitted rather than compared against the sentinel.
    """
    bounds: dict[str, object] = {}
    if lb is not Ellipsis:
        bounds["gt" if strict_lb else "ge"] = _bound(lb, "lower")
    if ub is not Ellipsis:
        bounds["lt" if strict_ub else "le"] = _bound(ub, "upper")
    if lb is not Ellipsis and ub is not Ellipsis:
        # Two ends each orderable against themselves can still be unorderable
        # against each other, and an interval whose ends cannot be compared
        # denotes no set of values.
        try:
            _ = lb <= ub  # ty: ignore[unsupported-operator]
        except TypeError as exc:
            msg = f"the bounds {lb!r} and {ub!r} do not support comparison"
            raise SchemaError(msg) from exc
    return _refine(_Marker(**bounds))


def size(lb: int, ub: int | EllipsisType | None = None) -> CompiledValidator:
    """Values whose ``len`` is bounded by ``lb`` and ``ub``.

    Following vtjson: a missing ``ub`` means exactly ``lb``, and ``ub`` of
    ``...`` means unbounded above.
    """
    low = _integer(lb, "lower size bound")
    if low < 0:
        msg = f"the lower size bound {low} is smaller than 0"
        raise SchemaError(msg)
    bounds: dict[str, object] = {"min_length": low}
    if ub is None:
        bounds["max_length"] = low
    elif ub is not Ellipsis:
        high = _integer(ub, "upper size bound")
        if high < low:
            msg = f"the lower size bound {low} is bigger than the upper bound {high}"
            raise SchemaError(msg)
        bounds["max_length"] = high
    return _refine(_Marker(**bounds))


def union(*schemas: object) -> CompiledValidator:
    """Return the union of the given schemas (a value matching any of them)."""
    return _union(*(_translate(s) for s in schemas))


def intersect(*schemas: object) -> CompiledValidator:
    """Return the intersection of the given schemas (matching all of them)."""
    return _intersect(*(_translate(s) for s in schemas))


def complement(schema: object) -> CompiledValidator:
    """Return the complement of the given schema (a value not matching it)."""
    return _complement(_translate(schema))


def ifthen(
    if_schema: object,
    then_schema: object,
    else_schema: object = None,
) -> CompiledValidator:
    """Require ``then_schema`` when a value matches ``if_schema``.

    Following vtjson, ``else_schema=None`` means there is no else-branch, so a
    value outside ``if_schema`` is admitted. Translating the ``None`` instead
    would demand the value *be* ``None``, inverting the construct.
    """
    if else_schema is None:
        else_schema = anything
    return _derived_ifthen(
        _translate(if_schema), _translate(then_schema), _translate(else_schema)
    )


def cond(*args: tuple[object, object]) -> CompiledValidator:
    """Select the ``then`` of the first matching ``(condition, then)`` case.

    vtjson has no default clause; a trailing ``(anything, then)`` case is how
    one is written, and an unmatched value is admitted.
    """
    for case in args:
        if not isinstance(case, tuple) or len(case) != 2:  # noqa: PLR2004
            msg = f"the case {case!r} is not a tuple of length two"
            raise SchemaError(msg)
    translated = [(_translate(c), _translate(t)) for c, t in args]
    return _derived_cond(*translated)


@_nullary
def float_() -> CompiledValidator:
    """Return the floats-only set (vtjson's ``float_``)."""
    return _validator(float)


@_nullary
def number() -> CompiledValidator:
    """Return the ints and the floats (vtjson's ``number``).

    vtjson's `number` is a deprecated alias for its `float` schema, which admits
    both, so the union matches its meaning exactly. valgebra keeps `float_` for
    the floats-only set.
    """
    return _union(_validator(int), _validator(float))


def _present(candidates: tuple[object, ...], obj: object) -> int | None:
    """Count how many candidates are keys of ``obj``, or ``None`` if it has none.

    The dict-key modifiers constrain a mapping. A value that is not one has no
    keys to count, which is a different answer from a count of zero: vtjson
    rejects it whatever the modifier's threshold is, so the two must not share
    an encoding.
    """
    if not isinstance(obj, Mapping):
        return None
    try:
        return sum(1 for k in candidates if k in obj)
    except Exception:  # noqa: BLE001  (a mapping that cannot answer has no such key)
        return None


def _counted(
    candidates: tuple[object, ...], obj: object, accept: Callable[[int], bool]
) -> bool:
    """Whether ``obj`` is a mapping whose count of ``candidates`` ``accept``s."""
    present = _present(candidates, obj)
    return present is not None and accept(present)


def keys(*required: object) -> CompiledValidator:
    """Require every listed key to be present."""
    return _predicate(lambda obj: _counted(required, obj, lambda n: n == len(required)))


def one_of(*candidates: object) -> CompiledValidator:
    """Require exactly one of the listed keys to be present."""
    return _predicate(lambda obj: _counted(candidates, obj, lambda n: n == 1))


def at_least_one_of(*candidates: object) -> CompiledValidator:
    """Require at least one of the listed keys to be present."""
    return _predicate(lambda obj: _counted(candidates, obj, lambda n: n >= 1))


def at_most_one_of(*candidates: object) -> CompiledValidator:
    """Require at most one of the listed keys to be present."""
    return _predicate(lambda obj: _counted(candidates, obj, lambda n: n <= 1))


@_nullary
def unique() -> CompiledValidator:
    """Require all elements of an iterable to be distinct."""
    return _predicate(_all_distinct)


def _all_distinct(obj: object) -> bool:
    try:
        items = list(obj)  # ty: ignore[invalid-argument-type]
    except TypeError:
        return False
    try:
        return len(items) == len({*items})
    except Exception:  # noqa: BLE001  (hashing is an optimisation, not the answer)
        # An element that cannot be hashed — for any reason, not only the
        # `TypeError` an unhashable type raises — is compared instead.
        return all(a != b for i, a in enumerate(items) for b in items[i + 1 :])


def div(divisor: int, remainder: int = 0, name: str | None = None) -> CompiledValidator:
    """Require an ``int`` with ``value % divisor == remainder`` (floats reject)."""
    del name  # accepted for vtjson signature parity; unused
    _integer(divisor, "divisor")
    _integer(remainder, "remainder")
    if divisor == 0:
        msg = "the divisor cannot be zero"
        raise SchemaError(msg)

    def check(obj: object) -> bool:
        if not isinstance(obj, int):
            return False
        try:
            # `(obj - remainder) % divisor`, not `obj % divisor == remainder`:
            # the two agree only where `remainder` is already the canonical
            # residue, and vtjson accepts any integer pair with a nonzero
            # divisor.
            return (obj - remainder) % divisor == 0
        except Exception:  # noqa: BLE001  (arithmetic that raises is not a residue)
            return False

    return _predicate(check)


def close_to(
    x: float,
    rel_tol: float | None = None,
    abs_tol: float | None = None,
) -> CompiledValidator:
    """Require ``value`` to be close to ``x`` (``math.isclose`` semantics)."""
    _number(x, "value")
    tolerances: dict[str, float] = {}
    if rel_tol is not None:
        tolerances["rel_tol"] = rel_tol
    if abs_tol is not None:
        tolerances["abs_tol"] = abs_tol

    def check(obj: object) -> bool:
        # `math.isclose` reads a `Decimal` or a `Fraction` happily; vtjson counts
        # neither as a number, so the type test decides before the tolerance does.
        if not isinstance(obj, int | float):
            return False
        try:
            return math.isclose(obj, x, **tolerances)
        except ValueError:
            # A tolerance `math.isclose` refuses does not make a value close.
            return False

    return _predicate(check)


def filter(  # noqa: A001  (mirrors vtjson's public name)
    filter: object,  # noqa: A002  (mirrors vtjson's parameter name)
    schema: object,
    filter_name: str | None = None,
) -> CompiledValidator:
    """Validate ``schema`` against ``filter(value)`` (a transform-then-check)."""
    del filter_name  # accepted for vtjson signature parity; unused
    if not callable(filter):
        msg = "the filter is not callable"
        raise SchemaError(msg)
    inner = _translate(schema)

    def check(obj: object) -> bool:
        try:
            return inner.is_valid(filter(obj))  # ty: ignore[call-top-callable]
        except Exception:  # noqa: BLE001  (any transform error means non-member)
            return False

    return _predicate(check)


def fields(d: Mapping[str, object]) -> CompiledValidator:
    """Require each attribute named in ``d`` to be present and match its schema."""
    if not isinstance(d, Mapping):
        msg = f"the attributes {d!r} are not a Mapping"
        raise SchemaError(msg)
    inner = {
        _text(name, "attribute name"): _translate(schema) for name, schema in d.items()
    }
    return _predicate(lambda obj: _attributes_match(inner, obj))


def protocol(schema: object, dict: bool = False) -> CompiledValidator:  # noqa: A002, FBT001, FBT002
    """Structurally check the type hints of ``schema`` (a class).

    By default the hints are checked against the value's attributes; with
    ``dict=True`` they are checked against a mapping's items. No ``isinstance``
    check is performed, mirroring vtjson — which is also how a `Protocol` and a
    `NamedTuple` written directly as a schema are read.
    """
    return _structural(schema, as_dict=dict)


def quote(schema: object) -> CompiledValidator:
    """Match ``schema`` as a literal by equality, not as a schema to interpret."""
    return _predicate(lambda obj: obj == schema)


def set_name(schema: object, name: str, reason: bool = False) -> CompiledValidator:  # noqa: FBT001, FBT002
    """Accept vtjson's ``set_name``; the name is cosmetic, so it is ignored."""
    _text(name, "name")
    del name, reason
    return _translate(schema)


def set_label(schema: object, *labels: str, debug: bool = False) -> CompiledValidator:
    """Accept vtjson's ``set_label``; the labels are ignored.

    Labels matter only with validate-time ``subs`` substitution, which is not
    supported — use the ``recursive`` fixpoint for recursion instead.
    """
    for label in labels:
        _text(label, "label")
    del labels, debug
    return _translate(schema)


def make_type(
    schema: object,
    name: str | None = None,
    strict: bool = True,  # noqa: FBT001, FBT002
    debug: bool = False,  # noqa: FBT001, FBT002
    subs: Mapping[str, object] | None = None,
) -> type:
    """Return an ``isinstance``-able type backed by the schema's validator.

    A non-empty ``subs`` is refused rather than ignored: silently dropping a
    substitution would build a type over a schema the caller did not ask for.
    """
    del debug
    if subs:
        msg = (
            "validate-time subs substitution is not supported; "
            "express recursion with valgebra's recursive fixpoint"
        )
        raise NotImplementedError(msg)
    validator = _translate(schema, open_records=not strict)

    class _Meta(type):
        def __instancecheck__(cls, instance: object) -> bool:
            return validator.is_valid(instance)

    return _Meta(name or "valgebra_type", (), {})


def safe_cast(schema: object, obj: object) -> object:
    """Validate ``obj`` against ``schema`` and return it unchanged."""
    return _translate(schema).ensure(obj)


def lax(schema: object) -> CompiledValidator:
    """Admit a key no clause of its record claims, throughout the subtree.

    Laxness settles only what happens to an *unclaimed* key. A record's named
    fields and its typed catch-all are clauses either way, so both still decide
    the keys they claim.
    """
    return _translate(schema, open_records=True)


def strict(schema: object) -> CompiledValidator:
    """Reject a key no clause of its record claims, throughout the subtree.

    That is what a translated schema already denotes, so this is the identity on
    a spec. It is not the identity on an already-built validator: a validator
    carries the mode it was built with, and vtjson's innermost wrapper is the one
    that decides.
    """
    return _translate(schema)
