"""Conformance: parity against the real fishtest schemas, fetched not vendored.

fishtest's ``server/fishtest/schemas.py`` has no license file (all rights
reserved), so it is deliberately NOT vendored into this repository. This test
fetches it at a pinned commit at run time, adapts it in memory by injecting the
schema-construct namespace (the same constructs, from vtjson on one side and the
compatibility layer on the other), and checks that the two agree on a document
corpus.

The test skips when offline. Every string-keyed schema and all six schema-keyed
tables — including worker_runs, whose value mixes a named key with a key-schema
catch-all (a heterogeneous map valgebra now expresses) — reach identical
accept/reject decisions.
"""

from __future__ import annotations

import datetime as dt
import re
import types
import urllib.error
import urllib.request

import pytest
import vtjson as vt

import vtjson_compat as vg

# The audited fishtest commit. Pinned so the schema cannot change under us.
_COMMIT = "66fd95217be9b1365d9432933d8e2f5f86c9ab0a"
_URL = (
    "https://raw.githubusercontent.com/official-stockfish/fishtest/"
    f"{_COMMIT}/server/fishtest/schemas.py"
)

# The vtjson constructs schemas.py imports; injected from whichever library.
_CONSTRUCTS = [
    "anything", "at_least_one_of", "at_most_one_of", "cond", "div", "email",
    "fields", "ge", "glob", "gt", "ifthen", "intersect", "ip_address", "keys",
    "lax", "magic", "nothing", "one_of", "quote", "regex", "regex_pattern",
    "set_label", "set_name", "size", "union", "unique",
]  # fmt: skip

# Top-level schemas with string keys.
_STRING_KEYED = [
    "pgns_schema", "user_schema", "kvstore_schema", "worker_schema", "nn_schema",
    "contributors_schema", "action_schema", "results_schema", "api_access_schema",
    "api_schema", "runs_schema", "worker_info_schema_api", "worker_info_schema_runs",
]  # fmt: skip

# Schemas that key a dict (or set) by a *schema*, not by string literals. All six
# translate and conform: single key-schema clauses, a single-element set, and —
# since valgebra grew heterogeneous maps — worker_runs, whose value mixes a named
# key with a key-schema catch-all.
_MAPPING_KEYED = [
    "cache_schema", "wtt_map_schema", "connections_counter_schema",
    "books_schema", "unfinished_runs_schema", "worker_runs_schema",
]  # fmt: skip

# A 24-hex string is a valid ObjectId, so a valid run_id / book / worker key.
_OID = "0123456789abcdef01234567"

# A worker-info document valid under worker_info_schema_api; the _runs variant
# adds remote_addr and country_code. Both sides accept it, exercising the accept
# path of these two schemas.
_WORKER_INFO_API = {
    "uname": "Linux", "architecture": ["64bit", "ELF"], "concurrency": 4,
    "max_memory": 8192, "min_threads": 1, "username": "user1", "version": 100,
    "python_version": [3, 14, 0], "gcc_version": [13, 2, 0], "compiler": "g++",
    "unique_key": "12345678-1234-5678-1234-567812345678", "modified": False,
    "worker_arch": "unknown", "ARCH": "x86_64", "nps": 1000000.0,
    "near_github_api_limit": False,
}  # fmt: skip
_WORKER_INFO_RUNS = {**_WORKER_INFO_API, "remote_addr": "1.2.3.4", "country_code": "?"}

# Per-schema documents, chosen so vtjson and the compat layer must agree. Each
# corpus exercises an accepted shape (often the empty mapping/set) and rejected
# shapes that fail on the key schema, the value schema, or the value structure.
_MAPPING_CORPUS: dict[str, list[object]] = {
    "connections_counter_schema": [
        {}, {"1.2.3.4": 5}, {"1.2.3.4": 0}, {"1.2.3.4": -1},
        {"not-an-ip": 5}, {"1.2.3.4": "x"},
    ],
    "wtt_map_schema": [
        {}, {"host-4cores-abcd": (_OID, 3)}, {"bad-name": (_OID, 3)},
        {"host-4cores-abcd": "not-a-tuple"},
    ],
    "unfinished_runs_schema": [set(), {_OID}, {"bad"}, {123}],
    "cache_schema": [{}, {"x": {}}, {_OID: "not-a-dict"}],
    "books_schema": [{}, {123: {}}, {"book.epd": "not-a-dict"}],
    "worker_runs_schema": [
        {}, {"host-4cores-abcd": {_OID: True, "last_run": _OID}},
        {"host-4cores-abcd": {_OID: 5, "last_run": _OID}},
        {"host-4cores-abcd": {_OID: True, "last_run": "short"}},
        {"host-4cores-abcd": {"not-hex": True, "last_run": _OID}},
    ],
}  # fmt: skip

_SUPPORTED_ARCHES = [
    "apple-silicon", "armv7", "armv7-neon", "armv8", "armv8-dotprod", "e2k",
    "general-32", "general-64", "loongarch64", "loongarch64-lasx",
    "loongarch64-lsx", "ppc-32", "ppc-64", "ppc-64-altivec", "ppc-64-vsx",
    "riscv64", "x86-32", "x86-32-sse2", "x86-32-sse41-popcnt", "x86-64",
    "x86-64-avx2", "x86-64-avx512", "x86-64-avxvnni", "x86-64-bmi2",
    "x86-64-sse3-popcnt", "x86-64-sse41-popcnt", "x86-64-ssse3", "x86-64-vnni512",
    "x86-64-avx512icl",
]  # fmt: skip
_SUPPORTED_COMPILERS = ["clang++", "g++"]


class _ObjectId:
    """A stand-in for ``bson.ObjectId`` (pymongo is not a dependency).

    Both sides inject the same class, so ``isinstance`` and ``is_valid`` give
    identical results regardless of the exact implementation; parity holds.
    """

    _HEX = re.compile(r"[0-9a-fA-F]{24}\Z")

    def __init__(self, oid: object = None) -> None:
        self.oid = oid

    @classmethod
    def is_valid(cls, oid: object) -> bool:
        if isinstance(oid, cls):
            return True
        if isinstance(oid, bytes):
            return len(oid) == 12
        return isinstance(oid, str) and cls._HEX.match(oid) is not None


def _fetch_source() -> str | None:
    try:
        with urllib.request.urlopen(_URL, timeout=15) as response:  # noqa: S310
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    # Drop the imports we inject into the namespace instead. A negated class
    # ([^)]*) already spans newlines, so the parenthesized imports need no
    # DOTALL (which would over-match the single-line ones).
    drop = [
        r"^from bson\.objectid import .*$",
        r"^from vtjson import \([^)]*\)",
        r"^from fishtest\.constants import \([^)]*\)",
        r"^import fishtest\.stats\.stat_util.*$",
    ]
    for pattern in drop:
        raw = re.sub(pattern, "", raw, flags=re.MULTILINE)
    return raw


def _build(lib: object, source: str) -> dict:
    """Execute the fishtest schema source with ``lib``'s constructs injected."""
    stat_util = types.SimpleNamespace(get_elo=lambda _results: (0.0, 0.0, 0.5))
    namespace: dict = {name: getattr(lib, name) for name in _CONSTRUCTS}
    # fishtest uses these nullary constructs bare; vtjson auto-instantiates a
    # bare construct class, so inject the instantiated form on both sides.
    for nullary in ("email", "unique", "regex_pattern"):
        namespace[nullary] = getattr(lib, nullary)()
    namespace.update(
        ObjectId=_ObjectId,
        PASSWORD_MAX_LENGTH=72,
        VALID_USERNAME_PATTERN="[A-Za-z0-9]{2,}",
        supported_arches=_SUPPORTED_ARCHES,
        supported_compilers=_SUPPORTED_COMPILERS,
        fishtest=types.SimpleNamespace(
            stats=types.SimpleNamespace(stat_util=stat_util)
        ),
    )
    exec(compile(source, "<fishtest_schemas>", "exec"), namespace)  # noqa: S102
    wanted = [*_STRING_KEYED, *_MAPPING_KEYED]
    return {name: namespace[name] for name in wanted if name in namespace}


def _accepts(validate, schema: object, obj: object) -> bool:
    try:
        validate(schema, obj)
    except (vt.ValidationError, vg.ValidationError):
        return False
    return True


def _corpus() -> list[object]:
    return [
        {},
        {"x": 1},
        "a string",
        42,
        [1, 2, 3],
        None,
        {"_id": _ObjectId()},
        {"_id": "k", "value": 1},  # valid kvstore document
        {"_id": "k", "value": {"nested": [1, 2]}},  # valid kvstore document
        {  # plausible user document
            "username": "ab",
            "password": "pw",
            "registration_time": dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
            "pending": False,
            "blocked": False,
            "email": "a@b.com",
            "groups": ["g1", "g2"],
            "tests_repo": "",
            "machine_limit": 4,
        },
        {  # plausible worker document
            "worker_name": "myhost-4cores-abcd12",
            "blocked": False,
            "message": "hi",
            "last_updated": dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
        },
        {"username": "", "password": "x"},  # invalid: username too short
        _WORKER_INFO_API,  # valid worker_info_schema_api
        _WORKER_INFO_RUNS,  # valid worker_info_schema_runs
    ]


def test_fishtest_upstream_parity() -> None:
    source = _fetch_source()
    if source is None:
        pytest.skip("the fishtest schema source is not reachable (offline)")
    try:
        vt_schemas = _build(vt, source)
        vg_schemas = _build(vg, source)
    except ImportError as exc:  # an optional format extra is not installed
        pytest.skip(f"optional dependency missing: {exc}")

    checked = 0
    accepted = 0
    unsupported: list[str] = []
    for name in _STRING_KEYED:
        if name not in vt_schemas or name not in vg_schemas:
            continue
        vt_schema, vg_schema = vt_schemas[name], vg_schemas[name]
        for document in _corpus():
            try:
                vg_ok = _accepts(vg.validate, vg_schema, document)
            except NotImplementedError:
                unsupported.append(name)
                break
            vt_ok = _accepts(vt.validate, vt_schema, document)
            assert vt_ok == vg_ok, f"{name}: {document!r} vtjson={vt_ok} compat={vg_ok}"
            checked += 1
            accepted += int(vt_ok)

    assert checked > 0, "no fishtest schema/document pairs were checked"
    assert accepted > 0, "no accept path was exercised; the corpus is too weak"
    # The shallow, string-keyed schemas must translate, not be reported as gaps.
    assert "kvstore_schema" not in unsupported
    assert "user_schema" not in unsupported
    assert "worker_schema" not in unsupported


def test_fishtest_upstream_mapping_keyed_parity() -> None:
    """All six schema-keyed tables translate and agree with vtjson."""
    source = _fetch_source()
    if source is None:
        pytest.skip("the fishtest schema source is not reachable (offline)")
    try:
        vt_schemas = _build(vt, source)
        vg_schemas = _build(vg, source)
    except ImportError as exc:  # an optional format extra is not installed
        pytest.skip(f"optional dependency missing: {exc}")

    checked = 0
    accepted = 0
    for name in _MAPPING_KEYED:
        if name not in vt_schemas or name not in vg_schemas:
            continue
        vt_schema, vg_schema = vt_schemas[name], vg_schemas[name]
        for document in _MAPPING_CORPUS[name]:
            # These must translate, not raise: that is the point of this test.
            vg_ok = _accepts(vg.validate, vg_schema, document)
            vt_ok = _accepts(vt.validate, vt_schema, document)
            assert vt_ok == vg_ok, f"{name}: {document!r} vtjson={vt_ok} compat={vg_ok}"
            checked += 1
            accepted += int(vt_ok)

    assert checked > 0, "no mapping-keyed schema/document pairs were checked"
    assert accepted > 0, "no accept path was exercised; the corpus is too weak"


def test_fishtest_covers_every_schema() -> None:
    """Every schema in the fishtest source is exercised — none silently untested.

    The tested set must equal the set of top-level ``*schema*`` definitions in the
    fetched source, so a future fishtest release that adds (or renames) a schema
    fails this test until it is classified and given a document corpus.
    """
    source = _fetch_source()
    if source is None:
        pytest.skip("the fishtest schema source is not reachable (offline)")
    in_source = set(re.findall(r"^(\w*schema\w*)\s*=", source, re.MULTILINE))
    tested = set(_STRING_KEYED) | set(_MAPPING_KEYED)
    assert in_source, "no schemas parsed from the fishtest source"
    assert in_source - tested == set(), (
        f"untested fishtest schemas: {sorted(in_source - tested)}"
    )
    assert tested - in_source == set(), (
        f"tested names absent from the source: {sorted(tested - in_source)}"
    )
