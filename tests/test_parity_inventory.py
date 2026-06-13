"""Parity inventory: no vtjson construct is silently missing.

Every name on vtjson's public surface is classified exactly once as:

- **supported** — the compatibility layer covers it (it is in ``vtjson_compat``);
- **ledgered** — a genuine vtjson schema construct deliberately not supported,
  recorded in ``docs/migrating-from-vtjson.md`` with a reason;
- **infrastructure** — not a vtjson schema construct at all: a re-exported stdlib
  module, a typing special form or generic alias, a feature flag, a ``TypeVar``,
  or an internal base class / error type.

The union of the three sets must equal vtjson's public surface *exactly*, so a
future vtjson release that adds or removes a name fails this test until a human
classifies it — that is the point: a new vtjson construct cannot slip in
unnoticed and unsupported.
"""

from __future__ import annotations

from pathlib import Path

import vtjson

import vtjson_compat

# Genuine vtjson schema constructs the layer covers. Each must be importable from
# vtjson_compat (asserted below).
_SUPPORTED = frozenset(
    {
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
    }
)

# Genuine vtjson schema constructs deliberately not supported. Each name must
# appear in the differences ledger (asserted below).
_LEDGERED = frozenset({"Apply", "skip_first"})

# Not vtjson schema constructs: re-exported stdlib, typing special forms and
# generic aliases, feature-detection flags, TypeVars, and internal base classes
# or error types. The typing generics (Mapping/Sequence/...) are the stdlib's,
# not vtjson inventions; the layer's support for typing annotations is exercised
# by the differential and compat suites, not catalogued here.
_INFRASTRUCTURE = frozenset(
    {
        # Re-exported stdlib modules.
        "datetime",
        "dns",
        "email_validator",
        "functools",
        "idna",
        "inspect",
        "ipaddress",
        "magic_",
        "math",
        "pathlib",
        "re",
        "sys",
        "typing",
        "urllib",
        "vtjson",
        "warnings",
        # Typing special forms, generic aliases, and helpers.
        "Annotated",
        "Any",
        "Callable",
        "Container",
        "EllipsisType",
        "Generic",
        "Iterable",
        "Literal",
        "Mapping",
        "NotRequired",
        "Protocol",
        "Required",
        "Sequence",
        "Set",
        "Sized",
        "Type",
        "TypeAliasType",
        "TypeGuard",
        "TypeVar",
        "Union",
        "UnionType",
        "annotations",
        "cast",
        "dataclass",
        "overload",
        # TypeVars vtjson exposes at module scope.
        "C",
        "K",
        "StringKeyType",
        "T",
        # Feature-detection flags.
        "HAS_MAGIC",
        "TYPE_CHECKING",
        "supports_Annotated",
        "supports_Generic_ABC",
        "supports_Generics",
        "supports_Literal",
        "supports_NotRequired",
        "supports_TypeAliasType",
        "supports_TypedDict",
        "supports_UnionType",
        "supports_structural",
        # Internal base classes and the schema-error type.
        "SchemaError",
        "comparable",
        "compiled_schema",
        "wrapper",
    }
)


def _public_surface() -> frozenset[str]:
    return frozenset(name for name in dir(vtjson) if not name.startswith("_"))


def test_classification_partitions_the_public_surface() -> None:
    classified = _SUPPORTED | _LEDGERED | _INFRASTRUCTURE
    surface = _public_surface()
    unclassified = surface - classified
    stale = classified - surface
    assert not unclassified, (
        f"vtjson exposes unclassified names: {sorted(unclassified)}. "
        "Classify each as supported, ledgered, or infrastructure."
    )
    assert not stale, (
        f"the inventory classifies names vtjson no longer exposes: {sorted(stale)}."
    )


def test_classification_sets_are_disjoint() -> None:
    assert not (_SUPPORTED & _LEDGERED)
    assert not (_SUPPORTED & _INFRASTRUCTURE)
    assert not (_LEDGERED & _INFRASTRUCTURE)


def test_supported_constructs_are_importable() -> None:
    missing = {name for name in _SUPPORTED if not hasattr(vtjson_compat, name)}
    assert not missing, (
        f"declared supported but absent from vtjson_compat: {sorted(missing)}"
    )
    exported = set(vtjson_compat.__all__)
    not_exported = _SUPPORTED - exported
    assert not not_exported, f"supported but not in __all__: {sorted(not_exported)}"


def test_ledgered_constructs_are_recorded_in_the_ledger() -> None:
    ledger = (
        Path(__file__).resolve().parent.parent / "docs" / "migrating-from-vtjson.md"
    )
    text = ledger.read_text(encoding="utf-8")
    missing = {name for name in _LEDGERED if name not in text}
    assert not missing, f"ledgered constructs absent from the ledger: {sorted(missing)}"
