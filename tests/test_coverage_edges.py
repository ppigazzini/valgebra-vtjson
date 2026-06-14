"""Edge-branch coverage for the compatibility layer.

These exercise the corners the construct- and format-level tests skip past: the
non-string reject paths of every format, the optional-dependency error, the
type-translation fallbacks, and the structural-check rejects. Where vtjson has a
defined behaviour for the same input, the case asserts parity against it rather
than asserting valgebra in isolation.
"""

import importlib
from dataclasses import dataclass

import pytest
import vtjson

import vtjson_compat as vg


def _vt(schema: object, value: object) -> bool:
    try:
        vtjson.validate(schema, value)
    except Exception:  # noqa: BLE001 - vtjson raises its own error type
        return False
    return True


def _vg(schema: object, value: object) -> bool:
    return vg.compile(schema).is_valid(value)


# --- Tuple shapes: fixed, homogeneous, and prefix-plus-tail -------------------


@pytest.mark.parametrize(
    ("schema", "value"),
    [
        ((str, int, ...), ("x",)),
        ((str, int, ...), ("x", 1, 2)),
        ((str, int, ...), ()),
        ((str, int, ...), (1,)),
        ((str, int, ...), ("x", "y")),
        ((int, ...), ()),
        ((int, ...), (1, 2, 3)),
        ((int, ...), ("x",)),
        ((int, str), (1, "a")),
        ((int, str), (1, 2)),
        ((int, str), (1,)),
    ],
)
def test_tuple_shapes_reach_parity(schema: tuple, value: tuple) -> None:
    assert _vg(schema, value) == _vt(schema, value)


# --- Set shapes: single, multi-element union, and empty -----------------------


@pytest.mark.parametrize(
    ("schema", "value"),
    [
        ({int}, set()),
        ({int}, {1}),
        ({int}, {"a"}),
        ({int, str}, set()),
        ({int, str}, {1, "a"}),
        ({int, str}, {1.5}),
        (set(), set()),
        (set(), {1}),
    ],
)
def test_set_shapes_reach_parity(schema: set, value: set) -> None:
    assert _vg(schema, value) == _vt(schema, value)


# --- Type translation fallbacks ----------------------------------------------


def test_none_type_translates_to_the_none_literal() -> None:
    assert _vg(type(None), None) is True
    assert _vg(type(None), 0) is False
    assert _vg(type(None), None) == _vt(type(None), None)


def test_bare_class_falls_back_to_an_isinstance_check() -> None:
    # A plain class (not a dataclass/Enum/TypedDict/Protocol) cannot be built as
    # a structured schema, so the layer mirrors vtjson's bare-type isinstance.
    class Widget:
        pass

    w = Widget()
    assert _vg(Widget, w) is True
    assert _vg(Widget, 5) is False
    assert _vg(Widget, w) == _vt(Widget, w)
    assert _vg(Widget, 5) == _vt(Widget, 5)


def test_empty_dict_matches_only_the_empty_mapping() -> None:
    assert _vg({}, {}) is True
    assert _vg({}, {"a": 1}) is False
    assert _vg({}, {}) == _vt({}, {})
    assert _vg({}, {"a": 1}) == _vt({}, {"a": 1})


def test_dataclass_translates_structurally() -> None:
    @dataclass
    class Point:
        x: int
        y: int

    assert _vg(Point, Point(1, 2)) is True
    assert _vg(Point, Point("a", 2)) is False  # ty: ignore[invalid-argument-type]


# --- Optional-dependency error path ------------------------------------------


def test_missing_optional_dependency_raises_a_clear_import_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # When the package backing a format is absent, the layer raises ImportError
    # with an install hint instead of a bare ModuleNotFoundError.
    def _absent(_name: str) -> object:
        msg = "simulated missing dependency"
        raise ImportError(msg)

    monkeypatch.setattr(importlib, "import_module", _absent)
    with pytest.raises(ImportError, match="valgebra-vtjson"):
        vg.email()


# --- Format reject branches: non-string and malformed inputs ------------------


@pytest.mark.parametrize(
    "validator",
    [
        vg.glob("*.py"),
        vg.regex_pattern(),
        vg.date_time(),
        vg.date(),
        vg.time(),
    ],
)
def test_string_formats_reject_non_strings(validator: vg.CompiledValidator) -> None:
    assert validator.is_valid(42) is False
    assert validator.is_valid(None) is False


def test_glob_with_an_empty_pattern_rejects_rather_than_raising() -> None:
    # An empty glob pattern makes PurePath.match raise; the layer turns that into
    # a clean reject, not a crash.
    assert vg.glob("").is_valid("anything") is False


def test_ip_address_rejects_a_non_address_type() -> None:
    # ipaddress accepts int/str/bytes; anything else is a non-member, not a crash.
    assert vg.ip_address().is_valid([1, 2, 3, 4]) is False
    assert vg.ip_address().is_valid("1.2.3.4") is True


def test_ip_address_rejects_an_unknown_version() -> None:
    with pytest.raises(ValueError, match="version is not 4 or 6"):
        vg.ip_address(5)


# --- Construct edge branches --------------------------------------------------


def test_close_to_honours_a_relative_tolerance() -> None:
    near = vg.close_to(1.0, rel_tol=0.01)
    assert near.is_valid(1.005) is True
    assert near.is_valid(1.5) is False


def test_protocol_dict_mode_rejects_a_non_mapping() -> None:
    class Shape:
        x: int
        y: int

    items = vg.protocol(Shape, dict=True)
    assert items.is_valid(42) is False  # not a mapping at all
    assert items.is_valid({"x": 1, "y": 2}) is True


def test_make_type_lax_admits_undeclared_keys() -> None:
    lax_type = vg.make_type({"x": int}, strict=False)
    assert isinstance({"x": 1, "extra": 2}, lax_type)
    assert not isinstance({"x": "bad"}, lax_type)


# --- Network formats and magic (optional extras) ------------------------------


def test_domain_name_resolve_rejects_an_unresolvable_name() -> None:
    pytest.importorskip("idna")
    pytest.importorskip("dns.resolver")
    checker = vg.domain_name(resolve=True)
    # A syntactically valid name under the reserved .invalid TLD never resolves.
    assert checker.is_valid("definitely-not-a-real-host.invalid") is False


def test_magic_rejects_a_non_buffer() -> None:
    pytest.importorskip("magic")
    checker = vg.magic("text/plain")
    assert checker.is_valid(42) is False  # neither str nor bytes
