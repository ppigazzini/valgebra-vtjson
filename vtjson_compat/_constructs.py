"""The vtjson combinators, refinements, modifiers, predicates, and wrappers.

Each mirrors a vtjson construct on top of the valgebra algebra. The dict
modifiers, structural checks, and numeric/sequence predicates are expressed as
predicates over any value (valgebra's documented slow path), so the
accept/reject decision matches vtjson; a predicate returns False on a type it
cannot handle, mirroring vtjson's reject.
"""

import math
from types import EllipsisType
from typing import get_type_hints

from ._translate import _DICT, _Marker, _nullary, _predicate, _refine, _translate
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
    lax as _lax,
)
from ._valgebra_api import (
    strict as _strict,
)
from ._valgebra_api import (
    union as _union,
)
from ._valgebra_api import (
    validator as _validator,
)


def gt(bound: object) -> CompiledValidator:
    """Values strictly greater than ``bound``."""
    return _refine(_Marker(gt=bound))


def ge(bound: object) -> CompiledValidator:
    """Values greater than or equal to ``bound``."""
    return _refine(_Marker(ge=bound))


def lt(bound: object) -> CompiledValidator:
    """Values strictly less than ``bound``."""
    return _refine(_Marker(lt=bound))


def le(bound: object) -> CompiledValidator:
    """Values less than or equal to ``bound``."""
    return _refine(_Marker(le=bound))


def interval(
    lower: object,
    upper: object,
    strict_lower: bool = False,  # noqa: FBT001, FBT002
    strict_upper: bool = False,  # noqa: FBT001, FBT002
) -> CompiledValidator:
    """Values in the interval between ``lower`` and ``upper``."""
    bounds: dict[str, object] = {}
    bounds["gt" if strict_lower else "ge"] = lower
    bounds["lt" if strict_upper else "le"] = upper
    return _refine(_Marker(**bounds))


def size(lower: int, upper: int | EllipsisType | None = None) -> CompiledValidator:
    """Values whose ``len`` is bounded by ``lower`` and ``upper``.

    Following vtjson: a missing ``upper`` means exactly ``lower``, and ``upper``
    of ``...`` means unbounded above.
    """
    bounds: dict[str, object] = {"min_length": lower}
    if upper is None:
        bounds["max_length"] = lower
    elif upper is not Ellipsis:
        bounds["max_length"] = upper
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
    condition: object,
    then: object,
    otherwise: object = anything,
) -> CompiledValidator:
    """Require ``then`` when a value matches ``condition``, else ``otherwise``."""
    return _derived_ifthen(
        _translate(condition), _translate(then), _translate(otherwise)
    )


def cond(
    *cases: tuple[object, object],
    default: object = anything,
) -> CompiledValidator:
    """Select the ``then`` of the first matching ``(condition, then)`` case."""
    translated = [(_translate(c), _translate(t)) for c, t in cases]
    return _derived_cond(*translated, default=_translate(default))


def float_() -> CompiledValidator:
    """Return the floats-only set (vtjson's ``float_``)."""
    return _validator(float)


def _present(candidates: tuple[object, ...], obj: object) -> int:
    """Count how many candidates are members of ``obj`` (by ``in``)."""
    try:
        return sum(1 for k in candidates if k in obj)  # ty: ignore[unsupported-operator]
    except TypeError:
        return 0


def keys(*required: object) -> CompiledValidator:
    """Require every listed key to be present (by ``in``)."""
    return _predicate(lambda obj: _present(required, obj) == len(required))


def one_of(*candidates: object) -> CompiledValidator:
    """Require exactly one of the listed keys to be present."""
    return _predicate(lambda obj: _present(candidates, obj) == 1)


def at_least_one_of(*candidates: object) -> CompiledValidator:
    """Require at least one of the listed keys to be present."""
    return _predicate(lambda obj: _present(candidates, obj) >= 1)


def at_most_one_of(*candidates: object) -> CompiledValidator:
    """Require at most one of the listed keys to be present."""
    return _predicate(lambda obj: _present(candidates, obj) <= 1)


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
    except TypeError:
        # Unhashable elements: fall back to a quadratic comparison.
        return all(a != b for i, a in enumerate(items) for b in items[i + 1 :])


def div(divisor: int, remainder: int = 0, name: str | None = None) -> CompiledValidator:
    """Require an ``int`` with ``value % divisor == remainder`` (floats reject)."""
    del name  # accepted for vtjson signature parity; unused

    def check(obj: object) -> bool:
        return isinstance(obj, int) and obj % divisor == remainder

    return _predicate(check)


def close_to(
    x: float,
    rel_tol: float | None = None,
    abs_tol: float | None = None,
) -> CompiledValidator:
    """Require ``value`` to be close to ``x`` (``math.isclose`` semantics)."""
    tolerances: dict[str, float] = {}
    if rel_tol is not None:
        tolerances["rel_tol"] = rel_tol
    if abs_tol is not None:
        tolerances["abs_tol"] = abs_tol

    def check(obj: object) -> bool:
        try:
            return math.isclose(obj, x, **tolerances)  # ty: ignore[invalid-argument-type]
        except TypeError:
            return False

    return _predicate(check)


def filter(  # noqa: A001  (mirrors vtjson's public name)
    transform: object,
    schema: object,
    filter_name: str | None = None,
) -> CompiledValidator:
    """Validate ``schema`` against ``transform(value)`` (a transform-then-check)."""
    del filter_name  # accepted for vtjson signature parity; unused
    inner = _translate(schema)

    def check(obj: object) -> bool:
        try:
            return inner.is_valid(transform(obj))  # ty: ignore[call-non-callable]
        except Exception:  # noqa: BLE001  (any transform error means non-member)
            return False

    return _predicate(check)


def fields(attributes: dict) -> CompiledValidator:
    """Require each named attribute to be present and match its schema."""
    inner = {name: _translate(schema) for name, schema in attributes.items()}
    return _predicate(lambda obj: _attributes_match(inner, obj))


def _attributes_match(inner: dict, obj: object) -> bool:
    for name, validator in inner.items():
        try:
            value = getattr(obj, name)
        except AttributeError:
            return False
        if not validator.is_valid(value):
            return False
    return True


def protocol(schema: object, dict: bool = False) -> CompiledValidator:  # noqa: A002, FBT001, FBT002
    """Structurally check the type hints of ``schema`` (a class).

    By default the hints are checked against the value's attributes; with
    ``dict=True`` they are checked against a mapping's items. No ``isinstance``
    check is performed, mirroring vtjson.
    """
    inner = {name: _translate(hint) for name, hint in get_type_hints(schema).items()}
    if dict:
        return _predicate(lambda obj: _items_match(inner, obj))
    return _predicate(lambda obj: _attributes_match(inner, obj))


def _items_match(inner: dict, obj: object) -> bool:
    if not isinstance(obj, _DICT):
        return False
    if any(key not in inner for key in obj):  # strict-closed: no undeclared keys
        return False
    return all(
        key in obj and validator.is_valid(obj[key]) for key, validator in inner.items()
    )


def quote(value: object) -> CompiledValidator:
    """Match the literal ``value`` by equality, not as a schema to interpret."""
    return _predicate(lambda obj: obj == value)


def set_name(schema: object, name: str, reason: bool = False) -> CompiledValidator:  # noqa: FBT001, FBT002
    """Accept vtjson's ``set_name``; the name is cosmetic, so it is ignored."""
    del name, reason
    return _translate(schema)


def set_label(schema: object, *labels: str, debug: bool = False) -> CompiledValidator:
    """Accept vtjson's ``set_label``; the labels are ignored.

    Labels matter only with validate-time ``subs`` substitution, which is not
    supported — use the ``lazy`` fixpoint for recursion instead.
    """
    del labels, debug
    return _translate(schema)


def make_type(
    schema: object,
    name: str | None = None,
    strict: bool = True,  # noqa: FBT001, FBT002
    debug: bool = False,  # noqa: FBT001, FBT002
) -> type:
    """Return an ``isinstance``-able type backed by the schema's validator."""
    del debug
    validator = _translate(schema)
    if not strict:
        validator = _lax(validator)

    class _Meta(type):
        def __instancecheck__(cls, instance: object) -> bool:
            return validator.is_valid(instance)

    return _Meta(name or "valgebra_type", (), {})


def safe_cast(schema: object, obj: object) -> object:
    """Validate ``obj`` against ``schema`` and return it unchanged."""
    return _translate(schema).ensure(obj)


def lax(schema: object) -> CompiledValidator:
    """Open every record in the schema's subtree (undeclared keys allowed)."""
    return _lax(_translate(schema))


def strict(schema: object) -> CompiledValidator:
    """Close every record in the schema's subtree (undeclared keys rejected)."""
    return _strict(_translate(schema))
