"""Unit tests for the vtjson compatibility layer, independent of vtjson itself.

These pin the compat contract (the float mapping, optionality, the supported and
not-yet-supported forms) without depending on the differential oracle.
"""

from dataclasses import dataclass

import pytest

import vtjson_compat as vg


def test_float_admits_ints_via_the_union_mapping():
    # vtjson's `float` also admits ints; the compat layer maps it accordingly.
    vg.validate(float, 5)
    vg.validate(float, 1.5)
    with pytest.raises(vg.ValidationError):
        vg.validate(float, "x")


def test_float_only_set():
    floats = vg.float_()
    assert floats.is_valid(1.5)
    assert not floats.is_valid(5)


def test_record_optional_key_convention():
    schema = {"name": str, "age?": int}
    vg.validate(schema, {"name": "Ada"})
    vg.validate(schema, {"name": "Ada", "age": 36})
    with pytest.raises(vg.ValidationError):
        vg.validate(schema, {"name": "Ada", "extra": 1})  # strict-closed
    assert vg.optional_key("age") == "age?"


def test_comparison_and_size_refinements():
    vg.validate(vg.gt(0), 5)
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.gt(0), 0)
    vg.validate(vg.interval(0, 10), 10)
    vg.validate(vg.size(2), "ab")  # exactly two
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.size(2), "abc")


def test_combinators_translate_their_members():
    vg.validate(vg.union(int, str), "x")
    vg.validate(vg.intersect(int, vg.complement(bool)), 5)
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.intersect(int, vg.complement(bool)), True)


def test_fixed_and_homogeneous_lists():
    # `[T]` is a one-element list; `[A, B]` is fixed-length; `[T, ...]` is
    # homogeneous; `[]` matches only the empty list.
    vg.validate([int], [5])
    with pytest.raises(vg.ValidationError):
        vg.validate([int], [5, 6])
    vg.validate([int, str], [1, "x"])
    with pytest.raises(vg.ValidationError):
        vg.validate([int, str], [1])
    vg.validate([int, ...], [1, 2, 3])
    vg.validate([], [])
    with pytest.raises(vg.ValidationError):
        vg.validate([], [1])


def test_dict_key_modifiers():
    vg.validate(vg.keys("a", "b"), {"a": 1, "b": 2, "c": 3})
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.keys("a", "b"), {"a": 1})
    vg.validate(vg.one_of("a", "b"), {"a": 1})
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.one_of("a", "b"), {"a": 1, "b": 2})
    vg.validate(vg.at_least_one_of("a", "b"), {"b": 2})
    vg.validate(vg.at_most_one_of("a", "b"), {})


def test_numeric_and_sequence_predicates():
    vg.validate(vg.unique(), [1, 2, 3])
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.unique(), [1, 1])
    vg.validate(vg.unique(), [[1], [2]])  # unhashable fallback
    vg.validate(vg.div(3), 9)
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.div(3), 9.0)  # floats reject, matching vtjson
    vg.validate(vg.close_to(1.0, abs_tol=0.2), 1.1)
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.close_to(1.0, abs_tol=0.2), 1.5)


@dataclass
class _Point:
    x: int
    y: int


def test_filter_fields_and_protocol():
    vg.validate(vg.filter(len, vg.ge(3)), "abcd")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.filter(len, vg.ge(3)), "ab")
    vg.validate(vg.fields({"x": int}), _Point(1, 2))
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.fields({"x": int}), _Point("a", 2))  # ty: ignore[invalid-argument-type]
    vg.validate(vg.protocol(_Point), _Point(1, 2))  # structural, no isinstance
    vg.validate(vg.protocol(_Point, dict=True), {"x": 1, "y": 2})
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.protocol(_Point, dict=True), {"x": 1, "y": 2, "z": 3})  # closed


def test_string_format_validators():
    vg.validate(vg.regex(r"\d+"), "123")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.regex(r"\d+"), "12a")  # full match by default
    vg.validate(vg.regex(r"\d+", fullmatch=False), "12a")
    vg.validate(vg.regex_pattern(), "[a-z]+")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.regex_pattern(), "[unclosed")
    vg.validate(vg.glob("*.py"), "a.py")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.glob("*.py"), "a.txt")
    vg.validate(vg.url(), "https://example.com")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.url(), "notaurl")
    vg.validate(vg.ip_address(), "1.2.3.4")
    vg.validate(vg.ip_address(6), "::1")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.ip_address(4), "::1")
    vg.validate(vg.date_time(), "2020-01-01T10:00:00")
    vg.validate(vg.date_time("%Y/%m/%d"), "2020/01/01")
    vg.validate(vg.date(), "2020-01-01")
    vg.validate(vg.time(), "10:00:00")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.date(), "2020-13-01")


def test_network_format_validators_optional_extra():
    pytest.importorskip("email_validator")
    pytest.importorskip("idna")
    vg.validate(vg.email(), "a@b.com")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.email(), "not-an-email")
    vg.validate(vg.domain_name(), "example.com")
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.domain_name(), "exa mple.com")
    # IDNA names need ascii_only=False
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.domain_name(), "bücher.de")
    vg.validate(vg.domain_name(ascii_only=False), "bücher.de")


def test_lax_and_strict_records():
    closed = vg.strict({"a": int})
    closed.validate({"a": 1})
    with pytest.raises(vg.ValidationError):
        closed.validate({"a": 1, "b": 2})
    open_record = vg.lax({"a": int})
    open_record.validate({"a": 1, "b": 2})  # undeclared key allowed
    with pytest.raises(vg.ValidationError):
        open_record.validate({"a": "x"})  # declared field still checked
    # lax is recursive
    vg.lax({"a": {"b": int}}).validate({"a": {"b": 1, "c": 2}})


def test_quote_set_name_set_label():
    vg.validate(vg.quote({"a": int}), {"a": int})  # the literal value, not a schema
    with pytest.raises(vg.ValidationError):
        vg.validate(vg.quote({"a": int}), {"a": 1})
    vg.validate(vg.set_name(int, "myint"), 1)  # name is cosmetic
    vg.validate(vg.set_label(int, "L"), 1)  # label is cosmetic


def test_make_type_and_safe_cast():
    int_type = vg.make_type(int)
    assert isinstance(5, int_type)
    assert not isinstance("x", int_type)
    assert vg.safe_cast(int, 5) == 5
    with pytest.raises(vg.ValidationError):
        vg.safe_cast(int, "x")


def test_magic_optional_extra():
    pytest.importorskip("magic")
    try:
        schema = vg.magic("application/pdf")
    except ImportError:
        pytest.skip("python-magic/libmagic not available")
    schema.validate(b"%PDF-1.4\n%test content")
    with pytest.raises(vg.ValidationError):
        schema.validate(b"plain text")


def test_compile_is_reusable():
    validator = vg.compile({"a": int})
    assert validator.is_valid({"a": 1})
    assert not validator.is_valid({"a": "x"})


def test_validate_lax_mode_and_subs():
    schema = {"a": int}
    vg.validate(schema, {"a": 1, "b": 2}, strict=False)  # lax: extra key allowed
    with pytest.raises(vg.ValidationError):
        vg.validate(schema, {"a": 1, "b": 2}, strict=True)  # closed by default
    vg.validate(int, 5, "label")  # name is accepted and cosmetic
    with pytest.raises(NotImplementedError):
        vg.validate(int, 5, subs={"x": int})  # subs is not supported


def test_prefix_tail_lists_and_heterogeneous_maps_are_supported():
    # Previously-ledgered structural gaps, now expressible through valgebra.
    # Prefix plus repeated tail: a str, then zero or more ints.
    vg.validate([str, int, ...], ["x"])
    vg.validate([str, int, ...], ["x", 1, 2])
    with pytest.raises(vg.ValidationError):
        vg.validate([str, int, ...], [1])  # the prefix must be a str
    # Several schema-valued key clauses (each key matches its own value schema).
    vg.validate({int: int, str: str}, {1: 2, "a": "b"})
    with pytest.raises(vg.ValidationError):
        vg.validate({int: int, str: str}, {1: "x"})
    # A named key mixed with a key-schema catch-all.
    vg.validate({"last_run": int, str: bool}, {"last_run": 5, "extra": True})
    with pytest.raises(vg.ValidationError):
        vg.validate({"last_run": int, str: bool}, {"extra": True})  # last_run required
