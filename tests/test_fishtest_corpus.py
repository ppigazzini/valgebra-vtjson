"""Differential parity over a fishtest-representative document corpus.

The schema in ``tests/fixtures/fishtest_like.py`` is built once with vtjson and
once with the compatibility layer; for every sample document the two must reach
the same accept/reject decision, and that decision must match the recorded
expectation so the corpus stays meaningful.
"""

import importlib.util
from pathlib import Path

import vtjson as vt

import vtjson_compat as vg

_FIXTURE = Path(__file__).parent / "fixtures" / "fishtest_like.py"
_spec = importlib.util.spec_from_file_location("fishtest_like", _FIXTURE)
assert _spec is not None
fishtest_like = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(fishtest_like)


def _accepts(validate, schema: object, obj: object) -> bool:
    try:
        validate(schema, obj)
    except (vt.ValidationError, vg.ValidationError):
        return False
    return True


def test_fishtest_like_corpus_parity() -> None:
    vt_schema = fishtest_like.build(vt)
    vg_schema = fishtest_like.build(vg)
    for index, (document, expected) in enumerate(fishtest_like.cases()):
        vt_ok = _accepts(vt.validate, vt_schema, document)
        vg_ok = _accepts(vg.validate, vg_schema, document)
        assert vt_ok == vg_ok, f"case {index}: vtjson={vt_ok} compat={vg_ok}"
        assert vt_ok == expected, f"case {index}: expected {expected}, got {vt_ok}"
