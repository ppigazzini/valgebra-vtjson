"""What valgebra can do that vtjson cannot.

vtjson validates a value against a schema and stops there. valgebra is a Boolean
algebra of schemas with a decision procedure, so beyond membership it reasons
*about schemas* — subtyping, equivalence, emptiness, and simplification — which
vtjson has no notion of. It also corrects vtjson's value-level mistakes: typed
singletons, a structured error model, and surfaced predicate failures. Each test
contrasts the two so the difference is concrete, not asserted.
"""

from typing import Annotated

import annotated_types as at
import pytest
import vtjson
from valgebra import (
    ValidationError,
    complement,
    intersect,
    lazy,
    simplify,
    union,
    validator,
)

import vtjson_compat as vg


def _vtjson_accepts(schema: object, value: object) -> bool:
    try:
        vtjson.validate(schema, value)
    except Exception:  # noqa: BLE001 - vtjson raises its own error type
        return False
    return True


# --- Value-level correctness: valgebra decides where vtjson is wrong ----------


def test_typed_singleton_literals_where_vtjson_conflates_by_equality() -> None:
    # vtjson matches a constant by Python ==, so the literal 1 wrongly accepts
    # True and 1.0 (and 0 accepts False).
    assert _vtjson_accepts(1, True)
    assert _vtjson_accepts(1, 1.0)
    assert _vtjson_accepts(0, False)
    # valgebra's literal is a typed singleton: same type and equal, nothing else.
    one = validator(1)
    assert one.is_valid(1)
    assert not one.is_valid(True)
    assert not one.is_valid(1.0)
    assert not validator(0).is_valid(False)


def test_structured_error_model_where_vtjson_gives_a_string() -> None:
    # vtjson raises a single human string. valgebra raises a machine-readable
    # model: a stable code and the path to the offending value.
    with pytest.raises(ValidationError) as info:
        vg.validate({"user": {"age": int}}, {"user": {"age": "old"}})
    err = info.value
    assert err.code == "int_type"
    assert err.path == ("user", "age")
    assert err.errors[0]["path"] == ("user", "age")


def test_raising_predicate_is_surfaced_where_vtjson_swallows_it() -> None:
    # A predicate that crashes is a distinct error in valgebra, not a silent
    # generic rejection.
    def boom(_value: object) -> bool:
        raise RuntimeError("buggy predicate")

    with pytest.raises(ValidationError) as info:
        validator(Annotated[int, at.Predicate(boom)]).validate(5)
    assert info.value.code == "predicate_error"


# --- Schema reasoning: capabilities vtjson does not have at all ---------------


def test_subtyping_is_a_valgebra_only_capability() -> None:
    # valgebra decides set inclusion between schemas; vtjson has no such notion.
    assert not hasattr(vtjson, "is_subtype")
    assert validator(bool).is_subtype(int)  # bool is a subtype of int
    assert validator(list[bool]).is_subtype(list[int])
    # Closed-record width: the narrower record is the subtype when the extra key
    # is optional ({x} fits inside {x, y?}); the reverse does not hold.
    assert validator({"x": int}).is_subtype({"x": int, "y?": str})
    assert not validator({"x": int, "y": str}).is_subtype({"x": int})
    assert not validator(int).is_subtype(bool)
    assert not validator(list[int]).is_subtype(list[str])


def test_equivalence_is_a_valgebra_only_capability() -> None:
    # Two differently-written schemas can be proven to denote the same set.
    assert union(bool, int).equivalent(int)  # bool | int is just int
    assert intersect(int, int).equivalent(int)
    assert not validator(int).equivalent(str)


def test_emptiness_detection_is_a_valgebra_only_capability() -> None:
    # An unsatisfiable schema is detected as such — including a recursive schema
    # with no base case, which no value can ever satisfy.
    assert intersect(int, complement(int)).is_empty()
    assert intersect(int, str).is_empty()
    assert lazy(lambda t: {"value": int, "next": t}).is_empty()  # no base case
    assert not validator(int).is_empty()
    assert not lazy(lambda t: union(None, {"next": t})).is_empty()  # base case


def test_simplification_is_a_valgebra_only_capability() -> None:
    # valgebra reduces a schema by the lattice laws without changing its meaning;
    # vtjson cannot manipulate a schema as an algebraic object at all.
    assert repr(simplify(complement(complement(int)))) == "int"
    assert repr(simplify(intersect(int, complement(int)))) == "nothing"
    assert repr(simplify(union(int, complement(int)))) == "anything"


def test_recursion_via_a_lazy_fixpoint() -> None:
    # valgebra ties recursion with an explicit fixpoint, decidable up front;
    # vtjson resolves a label by validate-time substitution.
    json_value = lazy(
        lambda j: union(None, bool, int, float, str, [j], {str: j}),
    )
    assert json_value.is_valid({"a": [1, "x", {"b": None}], "c": [True, 3.5]})
    assert not json_value.is_valid({"a": object()})
