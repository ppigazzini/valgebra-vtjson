"""A malformed schema is refused, not compiled into a validator that lies.

vtjson checks a construct's arguments when the schema is built and raises
``SchemaError``. A layer that skips the check does not merely report a different
exception: it returns a validator whose decision is wrong for every value. A
bound it cannot read is no bound, so the schema accepts everything; a pattern it
cannot use matches nothing, so the schema rejects everything. Neither says why.

Each row is calibrated against vtjson rather than against an expectation: the
row asserts nothing unless vtjson itself raises ``SchemaError`` for that call.
"""

from __future__ import annotations

from typing import Any

import pytest
import vtjson as vt

import vtjson_compat as vg


def _schema_error(module: Any, build: Any) -> BaseException | None:
    """Return the ``SchemaError`` ``build`` raises under ``module``, or ``None``."""
    error = getattr(module, "SchemaError", None)
    try:
        build(module)
    except BaseException as exc:  # noqa: BLE001  (the type is the assertion)
        return exc if error is not None and isinstance(exc, error) else None
    return None


# Each row is a construct call whose arguments are malformed. The builder runs
# once per library, so both columns are the same call.
MALFORMED: list[tuple[str, Any]] = [
    ("gt(None)", lambda m: m.gt(None)),
    ("ge(None)", lambda m: m.ge(None)),
    ("lt(None)", lambda m: m.lt(None)),
    ("le(None)", lambda m: m.le(None)),
    ("gt(complex)", lambda m: m.gt(complex(1, 2))),
    ("interval(1, 'a')", lambda m: m.interval(1, "a")),
    ("size(-1)", lambda m: m.size(-1)),
    ("size(5, 1)", lambda m: m.size(5, 1)),
    ("size(2.5)", lambda m: m.size(2.5)),
    ("div(0)", lambda m: m.div(0)),
    ("div('x')", lambda m: m.div("x")),
    ("div(2, 'x')", lambda m: m.div(2, "x")),
    ("close_to('x')", lambda m: m.close_to("x")),
    ("regex('(')", lambda m: m.regex("(")),
    ("regex('a', 5)", lambda m: m.regex("a", 5)),
    ("glob('')", lambda m: m.glob("")),
    ("glob(123)", lambda m: m.glob(123)),
    ("magic(123)", lambda m: m.magic(123)),
    ("ip_address(5)", lambda m: m.ip_address(5)),
    ("protocol(object)", lambda m: m.protocol(object)),
    ("fields(['a'])", lambda m: m.fields(["a"])),
    ("fields({5: int})", lambda m: m.fields({5: int})),
    ("filter(123, str)", lambda m: m.filter(123, str)),
    ("set_name(int, 123)", lambda m: m.set_name(int, 123)),
    ("set_label(int, 5)", lambda m: m.set_label(int, 5)),
    ("cond((int, str, float))", lambda m: m.cond((int, str, float))),
]

# Objects a schema is asked about. A malformed schema that answers the same way
# for every one of them is a schema that stopped discriminating.
PROBES: list[object] = [0, 1, -1, 1.5, "", "x", b"x", True, None, [], {}, (), object()]


def test_the_layer_publishes_a_schema_error() -> None:
    """``SchemaError`` is part of the surface a migrating caller catches."""
    assert issubclass(vg.SchemaError, Exception)


@pytest.mark.parametrize(
    ("label", "build"), MALFORMED, ids=[row[0] for row in MALFORMED]
)
def test_a_malformed_argument_is_refused(label: str, build: Any) -> None:
    """Whatever vtjson refuses to compile, the layer refuses too."""
    if _schema_error(vt, build) is None:
        pytest.skip(f"vtjson does not raise SchemaError for {label}")
    assert _schema_error(vg, build) is not None, (
        f"{label}: vtjson raises SchemaError, the layer does not"
    )


@pytest.mark.parametrize(
    ("label", "build"), MALFORMED, ids=[row[0] for row in MALFORMED]
)
def test_a_malformed_argument_never_yields_a_constant_verdict(
    label: str,
    build: Any,
) -> None:
    """A refused schema cannot become a validator that answers the same for everything.

    This is the failure the exception type alone does not describe. `gt(None)`
    accepting every object and `glob("")` rejecting every object are both silent:
    the caller sees a working validator, and only the answers are wrong.
    """
    if _schema_error(vt, build) is None:
        pytest.skip(f"vtjson does not raise SchemaError for {label}")
    try:
        schema = build(vg)
    except Exception:  # noqa: BLE001  (refusing to build is the outcome under test)
        return
    verdicts = {vg.compile(schema).is_valid(probe) for probe in PROBES}
    assert len(verdicts) > 1, (
        f"{label}: the layer built a schema that answers "
        f"{verdicts.pop()} for every probe"
    )
