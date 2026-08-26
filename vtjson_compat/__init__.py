"""vtjson compatibility layer.

Translate a vtjson-style schema into a valgebra validator and check membership,
so a vtjson schema validates with the same accept/reject decision. The
translation is honest about valgebra's algebra: where vtjson is lax, the lax
meaning is expressed with the combinators (for example vtjson's ``float``, which
also admits ints, becomes ``union(int, float)``) rather than by weakening a
primitive. A bare float *constant* is read the same way: vtjson matches one by
tolerance rather than identity, so the layer does too.

This package does not import the real ``vtjson`` package; it reimplements the
relevant surface on top of valgebra. Intentional behavioral differences are
recorded in the differences ledger (docs/03-conformance.md). Constructs
not yet supported raise ``NotImplementedError`` naming the gap.

Layout: ``_translate`` is the schema translator, ``_constructs`` the combinators
and predicates, ``_formats`` the string and network format validators; this
module is the public surface.

The supported surface is the one ``tests/test_parity_inventory.py`` classifies:
that file holds every vtjson public name to exactly one of supported, ledgered,
or not-a-construct, so it cannot fall out of step with the package the way a
list written here would.

A construct checks its own arguments when the schema is built and raises
``SchemaError`` when they cannot express a set of values, as vtjson does. The
check is not cosmetic: a bound valgebra cannot read contributes no constraint,
so the refinement would widen to every value rather than narrowing.

``compile`` builds a schema once into a reusable validator (vtjson's
compile-once path); ``validate`` recompiles per call, like vtjson's ``validate``.
Validate-time ``subs`` substitution is not supported: use the ``recursive`` fixpoint
for recursion instead.

Some names mirror vtjson's and shadow Python builtins (``compile``, ``filter``
and its ``filter=`` parameter, the ``dict=`` parameter of ``protocol``, the
``format=`` parameter of ``date_time``, the ``regex=`` parameter of ``regex``).
That is intentional: the layer is a vtjson drop-in, so it keeps vtjson's
spelling — argument names included — for mechanical migration. A call written
by keyword against vtjson's documentation runs here unchanged.
"""

from collections.abc import Mapping

from ._constructs import (
    at_least_one_of,
    at_most_one_of,
    close_to,
    complement,
    cond,
    div,
    fields,
    filter,  # noqa: A004  (mirrors vtjson's public name)
    float_,
    ge,
    gt,
    ifthen,
    intersect,
    interval,
    keys,
    lax,
    le,
    lt,
    make_type,
    number,
    one_of,
    protocol,
    quote,
    safe_cast,
    set_label,
    set_name,
    size,
    strict,
    union,
    unique,
)
from ._formats import (
    date,
    date_time,
    domain_name,
    email,
    glob,
    ip_address,
    magic,
    regex,
    regex_pattern,
    time,
    url,
)
from ._translate import SchemaError, _translate
from ._valgebra_api import CompiledValidator, ValidationError
from ._valgebra_api import (
    anything as _anything,
)
from ._valgebra_api import (
    nothing as _nothing,
)

# The lattice top and bottom, re-exported under the vtjson names.
anything = _anything
nothing = _nothing

__all__ = [
    "SchemaError",
    "ValidationError",
    "anything",
    "at_least_one_of",
    "at_most_one_of",
    "close_to",
    "compile",
    "complement",
    "cond",
    "date",
    "date_time",
    "div",
    "domain_name",
    "email",
    "fields",
    "filter",
    "float_",
    "ge",
    "glob",
    "gt",
    "ifthen",
    "intersect",
    "interval",
    "ip_address",
    "keys",
    "lax",
    "le",
    "lt",
    "magic",
    "make_type",
    "nothing",
    "number",
    "one_of",
    "optional_key",
    "protocol",
    "quote",
    "regex",
    "regex_pattern",
    "safe_cast",
    "set_label",
    "set_name",
    "size",
    "strict",
    "time",
    "union",
    "unique",
    "url",
    "validate",
]


def optional_key(key: str, _optional: bool = True) -> str:  # noqa: FBT001, FBT002
    """Mark a record key optional, using valgebra's ``"key?"`` convention.

    Following vtjson, ``_optional=False`` declares the key required, so a
    record's keys can be marked from a flag the caller computes.
    """
    return f"{key}?" if _optional else key


def compile(schema: object) -> CompiledValidator:  # noqa: A001  (vtjson's name)
    """Compile a vtjson-style ``schema`` once into a reusable validator.

    Mirrors vtjson's ``compile``: build the validator once and reuse it across
    many values, rather than recompiling on every ``validate`` call.
    """
    return _translate(schema)


def validate(
    schema: object,
    obj: object,
    name: str = "object",
    strict: bool = True,  # noqa: FBT001, FBT002
    subs: Mapping[str, object] | None = None,
) -> None:
    """Validate ``obj`` against a vtjson-style ``schema``.

    Raises valgebra's ``ValidationError`` on failure. ``name`` is accepted for
    vtjson signature parity and is cosmetic. ``strict=False`` opens every record
    (the lax mode). Validate-time ``subs`` substitution is not supported — use
    the ``recursive`` fixpoint for recursion.
    """
    del name  # accepted for vtjson signature parity; cosmetic
    if subs:
        msg = (
            "validate-time subs substitution is not supported; "
            "express recursion with valgebra's recursive fixpoint"
        )
        raise NotImplementedError(msg)
    _translate(schema, open_records=not strict).validate(obj)
