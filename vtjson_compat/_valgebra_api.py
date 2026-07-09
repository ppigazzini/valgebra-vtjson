"""Internal adapter onto the valgebra extension's current public surface.

This compatibility layer was first written against an earlier valgebra extension
API (``CompiledValidator``, ``validator``, ``intersect``, ``lax``, ``strict``,
``fixed_sequence``). The shipped valgebra exposes the validator class as
``Validator`` with a schema-spec constructor, the combinators ``union`` /
``intersection`` / ``complement`` / ``recursive``, the constants ``anything`` /
``nothing``, and ``Validator.open`` / ``Validator.close`` for the lax/strict
record modes. This module re-expresses the names the rest of the package uses in
terms of that surface, so the translator and constructs need no other change.
"""

from typing import Annotated

from valgebra._valgebra import (
    ValidationError,
    anything,
    complement,
    nothing,
    union,
)
from valgebra._valgebra import (
    Validator as CompiledValidator,
)
from valgebra._valgebra import (
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
    "intersect",
    "lax",
    "nothing",
    "strict",
    "union",
    "validator",
]


def validator(spec: object) -> CompiledValidator:
    """Compile a schema spec into a validator (the old ``validator`` builder)."""
    return CompiledValidator(spec)


class _ExactLen:
    """A length-bound marker valgebra reads by attribute (annotated-types style)."""

    def __init__(self, length: int) -> None:
        self.min_length = length
        self.max_length = length


def fixed_sequence(*elements: object) -> CompiledValidator:
    """Build a fixed-length list validator, matched positionally element by element.

    valgebra reads a multi-element list literal as a fixed-length positional list,
    but a single-element ``[T]`` as a *homogeneous* list, so a one-element fixed
    sequence is expressed as a homogeneous list pinned to length one.
    """
    if len(elements) == 1:
        return CompiledValidator(Annotated[list[elements[0]], _ExactLen(1)])  # ty: ignore[invalid-type-form]
    return CompiledValidator(list(elements))


def lax(value: CompiledValidator) -> CompiledValidator:
    """Open every record in ``value`` (lax mode), via ``Validator.open``."""
    return value.open()


def strict(value: CompiledValidator) -> CompiledValidator:
    """Close every record in ``value`` (strict mode), via ``Validator.close``."""
    return value.close()


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
