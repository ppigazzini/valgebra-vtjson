"""Differential parity against pinned vtjson 2.3.0.

The compatibility layer must reach the same accept or reject decision as vtjson
for every supported construct.

Each corpus entry pairs a schema spelled for vtjson with the equivalent spelling
for ``vtjson_compat`` (identical for the implicit forms both libraries read,
different for the named combinators). For every object, the two decisions must
match. Intentional, library-level differences are recorded in ``LEDGER`` and
asserted to differ exactly as documented; a new undocumented divergence fails.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
import vtjson as vt

import vtjson_compat as vg


@dataclass
class Point:
    x: int
    y: int


def _accepts(validate, schema: object, obj: object) -> bool:
    try:
        validate(schema, obj)
    except (vt.ValidationError, vg.ValidationError):
        return False
    return True


# Each row carries a label, the vtjson schema, the compat schema, then the
# objects to probe. For the implicit forms both libraries read the same Python
# value, so the two schema columns are the same object.
CORPUS: list[tuple[str, object, object, list[object]]] = [
    ("int", int, int, [0, 1, -5, True, 1.5, "1", None]),
    ("str", str, str, ["", "x", b"x", 1, None]),
    ("bytes", bytes, bytes, [b"", b"x", "x", 1]),
    ("bool", bool, bool, [True, False, 0, 1, "x"]),
    ("none", None, None, [None, 0, "", False]),
    # vtjson `float` admits ints; the compat layer maps it to union(int, float),
    # so the decisions match for both ints and floats.
    ("float", float, float, [1.5, 0.0, 5, True, "x", None]),
    ("const-str", "active", "active", ["active", "paused", "", 1]),
    ("const-int", 7, 7, [7, 8, "7"]),
    # homogeneous list
    ("list[int,...]", [int, ...], [int, ...], [[], [1, 2], [1, "x"], (1, 2), "x"]),
    # fixed-length and one-element lists, and the empty list
    ("list[int]", [int], [int], [[1], [], [1, 2], [1, "x"], (1,)]),
    ("list[int,str]", [int, str], [int, str], [[1, "x"], [1], [1, 2], "x"]),
    ("list[]", [], [], [[], [1], "x", {}]),
    # tuples: fixed and variadic
    ("tuple(int,str)", (int, str), (int, str), [(1, "a"), (1, 2), (1,), [1, "a"]]),
    ("tuple(int,...)", (int, ...), (int, ...), [(), (1, 2), (1, "x")]),
    # single-element set
    ("set{int}", {int}, {int}, [set(), {1, 2}, {1, "x"}, [1]]),
    # records: required and optional ("key?") keys, strict-closed
    (
        "record",
        {"name": str, "age?": int},
        {"name": str, "age?": int},
        [
            {"name": "Ada"},
            {"name": "Ada", "age": 36},
            {"name": "Ada", "age": "old"},
            {"name": "Ada", "extra": 1},
            {"age": 1},
            {},
        ],
    ),
    # mapping from a key type to a value type
    ("mapping", {str: int}, {str: int}, [{}, {"a": 1}, {"a": "x"}, {1: 2}]),
    # named combinators differ in spelling between the libraries
    ("union", vt.union(int, str), vg.union(int, str), [1, "x", 1.5, None]),
    (
        "intersect",
        vt.intersect(int, vt.complement(bool)),
        vg.intersect(int, vg.complement(bool)),
        [5, True, "x"],
    ),
    ("complement", vt.complement(int), vg.complement(int), [1, "x", None, True]),
    ("gt", vt.gt(0), vg.gt(0), [1, 0, -1, 5]),
    ("ge", vt.ge(0), vg.ge(0), [0, 1, -1]),
    ("le", vt.le(10), vg.le(10), [10, 11, 0]),
    ("interval", vt.interval(0, 10), vg.interval(0, 10), [0, 5, 10, -1, 11]),
    ("size", vt.size(1, 3), vg.size(1, 3), ["a", "abc", "", "abcd", [1], [1, 2, 3, 4]]),
    (
        "ifthen",
        vt.ifthen(int, vt.gt(0)),
        vg.ifthen(int, vg.gt(0)),
        [5, -1, "x"],
    ),
    (
        "cond",
        vt.cond((str, vt.size(1)), (int, vt.ge(0))),
        vg.cond((str, vg.size(1)), (int, vg.ge(0))),
        ["ok", "", 5, -1, 1.5],
    ),
    ("anything", vt.anything, vg.anything, [None, 0, "x", object()]),
    ("nothing", vt.nothing, vg.nothing, [None, 0, "x"]),
    # dict-key modifiers
    (
        "keys",
        vt.keys("a", "b"),
        vg.keys("a", "b"),
        [{"a": 1, "b": 2}, {"a": 1, "b": 2, "c": 3}, {"a": 1}, {}, [1, 2], 5],
    ),
    (
        "one_of",
        vt.one_of("a", "b"),
        vg.one_of("a", "b"),
        [{"a": 1}, {"a": 1, "b": 2}, {}],
    ),
    (
        "at_least_one_of",
        vt.at_least_one_of("a", "b"),
        vg.at_least_one_of("a", "b"),
        [{}, {"a": 1}, {"a": 1, "b": 2}],
    ),
    (
        "at_most_one_of",
        vt.at_most_one_of("a", "b"),
        vg.at_most_one_of("a", "b"),
        [{}, {"a": 1}, {"a": 1, "b": 2}],
    ),
    # numeric and sequence predicates
    (
        "unique",
        vt.unique(),
        vg.unique(),
        [[1, 2, 3], [1, 1], [[1], [1]], [[1], [2]], 5],
    ),
    ("div", vt.div(3), vg.div(3), [9, 8, 9.0, "x"]),
    ("div-rem", vt.div(3, 1), vg.div(3, 1), [7, 9, 10]),
    ("close_to", vt.close_to(1.0), vg.close_to(1.0), [1.0, 1.000000000_1, 1.1, "x"]),
    (
        "close_to-tol",
        vt.close_to(1.0, abs_tol=0.2),
        vg.close_to(1.0, abs_tol=0.2),
        [1.1, 1.5],
    ),
    # transform-then-check, and structural attribute/field checks
    (
        "filter",
        vt.filter(len, vt.ge(3)),
        vg.filter(len, vg.ge(3)),
        ["abcd", "ab", [1, 2, 3], 5],
    ),
    (
        "fields",
        vt.fields({"x": int}),
        vg.fields({"x": int}),
        [Point(1, 2), Point("a", 2), 5],  # ty: ignore[invalid-argument-type]
    ),
    (
        "protocol",
        vt.protocol(Point),
        vg.protocol(Point),
        [Point(1, 2), Point("a", 2), 5],  # ty: ignore[invalid-argument-type]
    ),
    (
        "protocol-dict",
        vt.protocol(Point, dict=True),
        vg.protocol(Point, dict=True),
        [{"x": 1, "y": 2}, {"x": 1, "y": "s"}, {"x": 1}, {"x": 1, "y": 2, "z": 3}],
    ),
    # string-format validators (same stdlib engines as vtjson)
    ("regex", vt.regex(r"\d+"), vg.regex(r"\d+"), ["123", "12a", "", 1]),
    (
        "regex-nofull",
        vt.regex(r"\d+", fullmatch=False),
        vg.regex(r"\d+", fullmatch=False),
        ["12a", "abc", "1"],
    ),
    (
        "regex_pattern",
        vt.regex_pattern(),
        vg.regex_pattern(),
        ["[a-z]+", "[unclosed", "", 5],
    ),
    ("glob", vt.glob("*.py"), vg.glob("*.py"), ["a.py", "a.txt", "x/b.py", 5]),
    (
        "url",
        vt.url(),
        vg.url(),
        ["https://example.com", "ftp://h/p", "notaurl", "http://", 5],
    ),
    (
        "ip_address",
        vt.ip_address(),
        vg.ip_address(),
        ["1.2.3.4", "::1", "999.1.1.1", "x", 1],
    ),
    ("ip_address-4", vt.ip_address(4), vg.ip_address(4), ["1.2.3.4", "::1"]),
    ("ip_address-6", vt.ip_address(6), vg.ip_address(6), ["::1", "1.2.3.4"]),
    (
        "date_time",
        vt.date_time(),
        vg.date_time(),
        ["2020-01-01T10:00:00", "2020-13-01", "x"],
    ),
    (
        "date_time-fmt",
        vt.date_time("%Y/%m/%d"),
        vg.date_time("%Y/%m/%d"),
        ["2020/01/01", "2020-01-01"],
    ),
    ("date", vt.date(), vg.date(), ["2020-01-01", "2020-13-01", "x"]),
    ("time", vt.time(), vg.time(), ["10:00:00", "25:00", "x"]),
    # wrappers: lax/strict (open vs closed records), quote, set_name/set_label
    (
        "lax",
        vt.lax({"a": int}),
        vg.lax({"a": int}),
        [{"a": 1}, {"a": 1, "b": 2}, {"a": "x"}, {}],
    ),
    (
        "lax-nested",
        vt.lax({"a": {"b": int}}),
        vg.lax({"a": {"b": int}}),
        [{"a": {"b": 1, "c": 2}}, {"a": {"b": "x"}}],
    ),
    (
        "strict",
        vt.strict({"a": int}),
        vg.strict({"a": int}),
        [{"a": 1}, {"a": 1, "b": 2}],
    ),
    ("quote", vt.quote({"a": int}), vg.quote({"a": int}), [{"a": int}, {"a": 1}, 5]),
    ("quote-type", vt.quote(int), vg.quote(int), [int, 5, "int"]),
    ("set_name", vt.set_name(int, "myint"), vg.set_name(int, "myint"), [1, "x"]),
    ("set_label", vt.set_label(int, "L"), vg.set_label(int, "L"), [1, "x"]),
    # network formats (vtjson already pulls email_validator/idna transitively)
    (
        "email",
        vt.email(),
        vg.email(),
        ["a@b.com", "a@b.co.uk", "not-an-email", "x@y", "a@b..com", "", 5],
    ),
    (
        "domain_name",
        vt.domain_name(),
        vg.domain_name(),
        ["example.com", "xn--n3h.com", "bücher.de", "exa mple.com", "", 5],
    ),
    (
        "domain_name-idna",
        vt.domain_name(ascii_only=False),
        vg.domain_name(ascii_only=False),
        ["example.com", "bücher.de", "exa mple.com", 5],
    ),
]


# Intentional, documented divergences: (label, vtjson schema, compat schema,
# object, reason). Each row is a place where valgebra deliberately decides
# differently from vtjson because vtjson is wrong; every row is asserted to
# actually diverge (so it cannot rot into silent agreement) and is mirrored in
# the user-facing ledger (docs/migrating-from-vtjson.md). Library-level
# differences that do NOT change the accept/reject decision (the structured
# error object, single- vs multi-error report, optional deps) stay in that doc
# only, not here.
LEDGER: list[tuple[str, object, object, object, str]] = [
    (
        "literal-bool",
        1,
        1,
        True,
        "vtjson accepts True for the constant 1 (Python ==, which conflates "
        "bool and int); valgebra rejects it — a literal is a typed singleton, "
        "and bool is not int",
    ),
]


def test_differential_parity_with_pinned_vtjson() -> None:
    failures: list[str] = []
    for label, vt_schema, vg_schema, objects in CORPUS:
        for obj in objects:
            vt_ok = _accepts(vt.validate, vt_schema, obj)
            vg_ok = _accepts(vg.validate, vg_schema, obj)
            if vt_ok != vg_ok:
                failures.append(f"{label}: {obj!r} -> vtjson={vt_ok} compat={vg_ok}")
    assert not failures, "undocumented divergences:\n" + "\n".join(failures)


def test_ledgered_divergences_actually_diverge() -> None:
    # A documented divergence that no longer diverges is stale: either vtjson
    # changed or valgebra regressed. Catch it instead of letting the ledger lie.
    for label, vt_schema, vg_schema, obj, _reason in LEDGER:
        vt_ok = _accepts(vt.validate, vt_schema, obj)
        vg_ok = _accepts(vg.validate, vg_schema, obj)
        assert vt_ok != vg_ok, f"{label}: ledgered divergence no longer diverges"


def test_magic_differential() -> None:
    pytest.importorskip("magic")
    try:
        vt_schema = vt.magic("application/pdf")
    except vt.SchemaError:
        pytest.skip("libmagic is not available")
    vg_schema = vg.magic("application/pdf")
    for obj in [b"%PDF-1.4\n%test content", b"plain text, not a pdf", "x"]:
        vt_ok = _accepts(vt.validate, vt_schema, obj)
        vg_ok = _accepts(vg.validate, vg_schema, obj)
        assert vt_ok == vg_ok


def test_ledger_cases_diverge_as_documented() -> None:
    for label, vt_schema, vg_schema, obj, reason in LEDGER:
        vt_ok = _accepts(vt.validate, vt_schema, obj)
        vg_ok = _accepts(vg.validate, vg_schema, obj)
        msg = f"{label} no longer diverges ({reason}); update the ledger"
        assert vt_ok != vg_ok, msg
