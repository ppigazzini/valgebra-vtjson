"""Random differential parity: vtjson versus the compatibility layer.

A property-based generator builds random schemas across the construct grammar
both libraries read, paired so the implicit forms share one object and the named
combinators are spelled for each library. For every schema and value, vtjson and
``vtjson_compat`` must reach the same accept/reject decision.

The generator deliberately avoids the cross-type constants (``0``/``1``/``True``/
``1.0``) whose equality vtjson conflates and valgebra does not: that single
divergence is the documented decision difference, pinned in ``test_differential``
and the ledger, so excluding it here lets this suite assert *zero* divergence and
flag anything else as a real one. A construct the layer does not support yet
(it raises ``NotImplementedError``) is skipped, not failed.
"""

from __future__ import annotations

import vtjson as vt
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

import vtjson_compat as vg


def _accepts(validate, schema: object, value: object) -> bool:
    try:
        validate(schema, value)
    except (vt.ValidationError, vg.ValidationError):
        return False
    return True


# Constants chosen so no value of one type equals a value of another type, so the
# typed-singleton-versus-Python-equality difference cannot fire.
_CONSTS = st.sampled_from(["a", "bb", 7, -3, 42, 2.5])
_SCALARS = st.sampled_from([int, str, bool, float, bytes, None])
_HASHABLE = st.one_of(_SCALARS, _CONSTS).map(lambda x: (x, x))


def _bounds() -> st.SearchStrategy[tuple[object, object]]:
    return st.integers(-5, 5).flatmap(
        lambda k: st.sampled_from(
            [
                (vt.gt(k), vg.gt(k)),
                (vt.ge(k), vg.ge(k)),
                (vt.lt(k), vg.lt(k)),
                (vt.le(k), vg.le(k)),
            ]
        )
    )


def _schemas() -> st.SearchStrategy[tuple[object, object]]:
    base = st.one_of(_HASHABLE, _bounds())
    return st.recursive(
        base,
        lambda child: st.one_of(
            child.map(lambda p: ([p[0]], [p[1]])),  # [T]
            child.map(lambda p: ([p[0], ...], [p[1], ...])),  # [T, ...]
            st.tuples(child, child).map(
                lambda ab: (
                    [ab[0][0], ab[1][0], ...],
                    [ab[0][1], ab[1][1], ...],
                )
            ),  # [A, B, ...] prefix plus repeated tail
            _HASHABLE.map(lambda p: ({p[0]}, {p[1]})),  # {T} (hashable inner)
            st.tuples(_HASHABLE, _HASHABLE).map(
                lambda ab: ({ab[0][0], ab[1][0]}, {ab[0][1], ab[1][1]})
            ),  # {A, B} multi-element set (every member matches A or B)
            child.map(lambda p: ({str: p[0]}, {str: p[1]})),  # {str: V} mapping
            child.map(
                lambda p: ({vt.regex(r"\d+"): p[0]}, {vg.regex(r"\d+"): p[1]})
            ),  # schema-key map
            st.tuples(child, child).map(
                lambda ab: (
                    {str: ab[0][0], int: ab[1][0]},
                    {str: ab[0][1], int: ab[1][1]},
                )
            ),  # {str: V1, int: V2} multi-clause map (disjoint key types)
            st.tuples(child, child).map(
                lambda ab: (
                    {"a": ab[0][0], int: ab[1][0]},
                    {"a": ab[0][1], int: ab[1][1]},
                )
            ),  # {"a": V1, int: V2} named field plus a key-schema catch-all
            st.tuples(child, child).map(
                lambda ab: ((ab[0][0], ab[1][0]), (ab[0][1], ab[1][1]))
            ),  # (A, B) fixed-length tuple
            child.map(lambda p: ((p[0], ...), (p[1], ...))),  # (T, ...) tuple
            st.tuples(child, child).map(
                lambda ab: (
                    (ab[0][0], ab[1][0], ...),
                    (ab[0][1], ab[1][1], ...),
                )
            ),  # (A, B, ...) prefix plus repeated tail tuple
            st.tuples(child, child).map(
                lambda ab: (
                    {"a": ab[0][0], "b?": ab[1][0]},
                    {"a": ab[0][1], "b?": ab[1][1]},
                )
            ),  # record
            st.tuples(child, child).map(
                lambda ab: (vt.union(ab[0][0], ab[1][0]), vg.union(ab[0][1], ab[1][1]))
            ),
            st.tuples(child, child).map(
                lambda ab: (
                    vt.intersect(ab[0][0], ab[1][0]),
                    vg.intersect(ab[0][1], ab[1][1]),
                )
            ),
            child.map(lambda p: (vt.complement(p[0]), vg.complement(p[1]))),
        ),
        max_leaves=10,
    )


def _values() -> st.SearchStrategy[object]:
    leaf = st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(max_size=4),
        st.binary(max_size=4),
    )
    return st.recursive(
        leaf,
        lambda child: st.one_of(
            st.lists(child, max_size=4),
            st.tuples(child, child),
            st.dictionaries(
                st.one_of(st.text(max_size=3), st.integers(-5, 5)), child, max_size=3
            ),
            st.frozensets(st.integers(), max_size=3),
        ),
        max_leaves=8,
    )


@settings(max_examples=500, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(pair=_schemas(), value=_values())
def test_random_schemas_agree_with_vtjson(
    pair: tuple[object, object], value: object
) -> None:
    vt_schema, vg_schema = pair
    try:
        compat = _accepts(vg.validate, vg_schema, value)
    except NotImplementedError:
        assume(False)  # an unsupported construct: out of scope here, see the ledger
        return
    assert _accepts(vt.validate, vt_schema, value) == compat
