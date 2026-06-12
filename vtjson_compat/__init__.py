"""vtjson compatibility layer.

Translate a vtjson-style schema into a valgebra validator and check membership,
so a vtjson schema validates with the same accept/reject decision. The
translation is honest about valgebra's algebra: where vtjson is lax, the lax
meaning is expressed with the combinators (for example vtjson's ``float``, which
also admits ints, becomes ``union(int, float)``) rather than by weakening a
primitive.

This package does not import the real ``vtjson`` package; it reimplements the
relevant surface on top of valgebra. Intentional behavioral differences are
recorded in the differences ledger (docs/migrating-from-vtjson.md). Constructs
not yet supported raise ``NotImplementedError`` naming the gap.

Layout: ``_translate`` is the schema translator, ``_constructs`` the combinators
and predicates, ``_formats`` the string and network format validators; this
module is the public surface.

Currently supported: scalars (with the ``float``/``float_`` mapping), ``None``,
constants, ``anything``/``nothing``, ``union``/``intersect``/``complement``,
homogeneous ``[T, ...]`` and fixed-length ``[A, B]`` lists, fixed and variadic
tuples, single-element sets, records (with the ``"key?"`` optional convention),
``{KeyType: ValueType}`` mappings, the comparison and size refinements
(``gt``/``ge``/``lt``/``le``/``interval``/``size``), ``ifthen``/``cond``, the
dict-key modifiers (``keys``/``one_of``/``at_least_one_of``/``at_most_one_of``),
``fields``/``protocol`` structural checks, the ``filter``/``unique``/``div``/
``close_to`` predicates, the string-format validators (``regex``/
``regex_pattern``/``glob``/``url``/``ip_address``/``date_time``/``date``/
``time``), the network formats (``email``/``domain_name`` via the
``valgebra-vtjson[formats]`` extra, ``magic`` via ``valgebra-vtjson[magic]``),
and the wrappers (``lax``/``strict``/``quote``/``set_name``/``set_label``/
``make_type``/``safe_cast``).

``compile`` builds a schema once into a reusable validator (vtjson's
compile-once path); ``validate`` recompiles per call, like vtjson's ``validate``.
Validate-time ``subs`` substitution is not supported: use the ``lazy`` fixpoint
for recursion instead.

Some names mirror vtjson's and shadow Python builtins (``compile``, ``filter``,
the ``dict=`` parameter of ``protocol``, the ``format=`` parameter of
``date_time``). That is intentional: the layer is a vtjson drop-in, so it keeps
vtjson's spelling for mechanical migration.
"""

from valgebra._valgebra import CompiledValidator, ValidationError
from valgebra._valgebra import (
    anything as _anything,
)
from valgebra._valgebra import (
    lax as _lax,
)
from valgebra._valgebra import (
    nothing as _nothing,
)

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
from ._translate import _translate

# The lattice top and bottom, re-exported under the vtjson names.
anything = _anything
nothing = _nothing

__all__ = [
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


def optional_key(key: str) -> str:
    """Mark a record key optional, using valgebra's ``"key?"`` convention."""
    return f"{key}?"


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
    subs: dict | None = None,
) -> None:
    """Validate ``obj`` against a vtjson-style ``schema``.

    Raises valgebra's ``ValidationError`` on failure. ``name`` is accepted for
    vtjson signature parity and is cosmetic. ``strict=False`` opens every record
    (the lax mode). Validate-time ``subs`` substitution is not supported — use
    the ``lazy`` fixpoint for recursion.
    """
    del name  # accepted for vtjson signature parity; cosmetic
    if subs:
        msg = "validate-time subs substitution is not supported; use lazy for recursion"
        raise NotImplementedError(msg)
    validator = _translate(schema)
    if not strict:
        validator = _lax(validator)
    validator.validate(obj)
