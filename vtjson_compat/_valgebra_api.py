"""The valgebra names the rest of the package uses, under the names it uses.

Everything here comes from the ``valgebra`` package, never from the
``valgebra._valgebra`` extension module underneath it: what that module exports
is an implementation detail, while ``valgebra.__all__`` is the surface valgebra
supports. The aliases exist so the translator and the constructs read in vtjson's
vocabulary — ``intersect`` rather than ``intersection``, a ``validator`` builder
rather than a class — and nothing else in the package imports valgebra directly.

A bound reaches valgebra as an ``annotated_types`` marker, the one constraint
vocabulary valgebra reads: a marker of any other class is metadata it ignores,
whatever attributes it carries, so ``refined`` is where every bound is built.
"""

from typing import Annotated, Any

import annotated_types as at
from valgebra import (
    ValidationError,
    anything,
    complement,
    instance_of,
    nothing,
    recursive,
    union,
)
from valgebra import (
    Validator as CompiledValidator,
)
from valgebra import (
    intersection as intersect,
)

__all__ = [
    "CompiledValidator",
    "ValidationError",
    "anything",
    "complement",
    "cond",
    "fixed_sequence",
    "ifthen",
    "instance_of",
    "intersect",
    "nothing",
    "recursive",
    "refined",
    "union",
    "validator",
]


def validator(spec: object) -> CompiledValidator:
    """Compile a schema spec into a validator (the old ``validator`` builder)."""
    return CompiledValidator(spec)


# The marker each bound is written as, by the name vtjson's constructs give it.
_BOUNDS = {
    "ge": at.Ge,
    "gt": at.Gt,
    "le": at.Le,
    "lt": at.Lt,
    "min_length": at.MinLen,
    "max_length": at.MaxLen,
}


def refined(**bounds: Any) -> CompiledValidator:
    """Build a validator for ``object`` narrowed by each of ``bounds``.

    Each bound is written as its ``annotated_types`` marker -- ``ge=0`` as
    ``Ge(0)`` -- since valgebra reads constraints off that vocabulary alone. No
    bound at all is ``object`` itself, which `Annotated` cannot spell. A bound
    arrives already checked by the construct that names it, which is why it is
    typed loosely here and strictly nowhere else.
    """
    markers = tuple(_BOUNDS[name](value) for name, value in bounds.items())
    if not markers:
        return CompiledValidator(object)
    return CompiledValidator(Annotated[(object, *markers)])


def fixed_sequence(*elements: object) -> CompiledValidator:
    """Build a fixed-length list validator, matched positionally element by element.

    valgebra reads a multi-element list literal as a fixed-length positional list,
    but a single-element ``[T]`` as a *homogeneous* list, so a one-element fixed
    sequence is expressed as a homogeneous list pinned to length one.
    """
    if len(elements) == 1:
        one = Annotated[list[elements[0]], at.MinLen(1), at.MaxLen(1)]  # ty: ignore[invalid-type-form]
        return CompiledValidator(one)
    return CompiledValidator(list(elements))


def ifthen(
    condition: object,
    then: object,
    otherwise: object = anything,
) -> CompiledValidator:
    """Require ``then`` when a value matches ``condition``, else ``otherwise``.

    Denotation ``(condition and then) or ((not condition) and otherwise)``;
    composed from the core algebra, replacing valgebra's dropped derived
    combinator. With the default ``otherwise`` this is "condition implies then".
    """
    return union(
        intersect(condition, then),
        intersect(complement(condition), otherwise),
    )


def cond(
    *cases: tuple[object, object],
    default: object = anything,
) -> CompiledValidator:
    """Select the ``then`` of the first matching ``(condition, then)`` case.

    Nests :func:`ifthen` from the last case inward, so the earliest matching case
    wins; an unmatched value must satisfy ``default``.
    """
    result: object = default
    for condition, then in reversed(cases):
        result = ifthen(condition, then, result)
    if isinstance(result, CompiledValidator):
        return result
    # No cases: coerce a bare default spec into a validator.
    return union(result)
