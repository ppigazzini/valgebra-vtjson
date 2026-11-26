"""Conformance: parity against the real fishtest schemas, fetched not vendored.

fishtest's ``server/fishtest/schemas.py`` has no license file (all rights
reserved), so it is deliberately NOT vendored into this repository. This test
fetches it at a pinned commit at run time, adapts it in memory by injecting the
schema-construct namespace (the same constructs, from vtjson on one side and the
compatibility layer on the other), and checks that the two agree on a document
corpus.

The test skips when offline. Every string-keyed schema is seeded with documents
written for this test, which both engines accept, and every mutation of a seed
reaches vtjson's decision but the conformance ledger's typed-singleton rows. All
six schema-keyed tables — including worker_runs, whose value mixes a named key
with a key-schema catch-all (a heterogeneous map valgebra now expresses) — reach
identical accept/reject decisions.
"""

from __future__ import annotations

import copy
import datetime as dt
import gzip
import json
import math
import re
import types
import urllib.error
import urllib.request
import warnings

import pytest
import vtjson as vt

import vtjson_compat as vg

# The audited fishtest commit. Pinned so the schema cannot change under us.
_COMMIT = "66fd95217be9b1365d9432933d8e2f5f86c9ab0a"
_URL = (
    "https://raw.githubusercontent.com/official-stockfish/fishtest/"
    f"{_COMMIT}/server/fishtest/schemas.py"
)

# The same file on fishtest's master, and the commits that last touched it: read
# only to say when master holds another schemas.py than the pin.
_MASTER_URL = (
    "https://raw.githubusercontent.com/official-stockfish/fishtest/"
    "master/server/fishtest/schemas.py"
)
_HISTORY_URL = (
    "https://api.github.com/repos/official-stockfish/fishtest/commits"
    "?path=server/fishtest/schemas.py&per_page=1"
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


def _fetched(url: str) -> str | None:
    """Return the text at ``url``, or `None` where it cannot be read."""
    try:
        with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def _fetch_source() -> str | None:
    raw = _fetched(_URL)
    if raw is None:
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


# Seed documents, written for this test: each is accepted by both engines, and
# its mutations probe the schema around it. Nothing of fishtest's is copied; the
# field names are the schema's own.
_SEED_TIME = dt.datetime(2025, 6, 7, 8, 9, 10, tzinfo=dt.UTC)
_SEED_RUN = "seed-c0ffee1"
_SEED_LONG_WORKER = "seedhost-8cores-qz12-c0de"
_SEED_SHORT_WORKER = "seedhost-8cores-qz12"
_SEED_NET = "nn-0123456789ab.nnue"
_SEED_RESULTS = {
    "wins": 1, "losses": 1, "draws": 0, "crashes": 0, "time_losses": 0,
    "pentanomial": [0, 0, 1, 0, 0],
}  # fmt: skip
_SEED_ARGS = {
    "base_tag": "main", "new_tag": "trial", "base_nets": [_SEED_NET],
    "new_nets": ["nn-0123456789ac.nnue"], "num_games": 2, "tc": "8+0.08",
    "new_tc": "8+0.08", "book": "seed.epd", "book_depth": "6", "threads": 1,
    "resolved_base": "c" * 40, "resolved_new": "d" * 40, "msg_base": "base",
    "msg_new": "trial", "base_options": "Hash=8", "new_options": "Hash=8",
    "info": "", "base_signature": "4242", "new_signature": "4243",
    "username": "seeder", "tests_repo": "https://github.com/seeder/engine",
    "auto_purge": False, "throughput": 100.0, "itp": 100.0, "priority": 0.0,
    "adjudication": True,
}  # fmt: skip
_SEED_REF = {"run_id": _OID, "run": _SEED_RUN}
_SEED_TASK = {"worker": _SEED_LONG_WORKER, "task_id": 3}
_SEED_ACTIONS = {
    "failed_task": {**_SEED_REF, **_SEED_TASK, "message": "lost"},
    "crash_or_time": {**_SEED_REF, **_SEED_TASK, "message": "late"},
    "dead_task": {**_SEED_REF, **_SEED_TASK},
    "system_event": {"message": "restart"},
    "new_run": {**_SEED_REF, "message": "queued"},
    "upload_nn": {"nn": _SEED_NET},
    "modify_run": {**_SEED_REF, "message": "edited"},
    "delete_run": _SEED_REF,
    "stop_run": {**_SEED_REF, "message": "halted"},
    "finished_run": {**_SEED_REF, "message": "done"},
    "approve_run": {**_SEED_REF, "message": "approved"},
    "purge_run": {**_SEED_REF, "message": "purged"},
    "block_user": {"user": "someone", "message": "blocked"},
    "accept_user": {"user": "someone", "message": "accepted"},
    "block_worker": {"worker": _SEED_SHORT_WORKER, "message": "blocked"},
    "log_message": {"message": "note"},
    "worker_log": {"worker": _SEED_LONG_WORKER, "message": "note"},
}  # fmt: skip


def _seeds() -> dict[str, list[object]]:
    """Each string-keyed schema's seed documents, built fresh for each use."""
    pgn = gzip.compress(b'[Event "seed"]\n', mtime=0)
    net = {"downloads": 7, "name": _SEED_NET, "user": "seeder"}
    tested = {
        **net,
        "is_master": True,
        "first_test": {"date": _SEED_TIME, "id": _OID},
        "last_test": {"date": _SEED_TIME, "id": _OID},
    }
    task = {
        "num_games": 2, "active": False, "last_updated": _SEED_TIME, "start": 0,
        "stats": _SEED_RESULTS, "worker_info": _WORKER_INFO_RUNS,
    }  # fmt: skip
    run = {
        "_id": _ObjectId(), "version": 24, "start_time": _SEED_TIME,
        "last_updated": _SEED_TIME, "tc_base": 8.0, "approved": True,
        "approver": "seeder", "finished": True, "deleted": False, "failed": False,
        "failures": 0, "is_green": False, "is_yellow": False, "workers": 0,
        "cores": 0, "committed_games": 2, "total_games": 2, "results": _SEED_RESULTS,
        "nps": 0.0, "games_per_minute": 0.0, "args": _SEED_ARGS, "tasks": [task],
        "bad_tasks": [],
    }  # fmt: skip
    actions: list[object] = [
        {
            "_id": _ObjectId(),
            "time": 1.5,
            "action": name,
            "username": "fishtest.system" if name == "system_event" else "seeder",
            **fields,
        }
        for name, fields in _SEED_ACTIONS.items()
    ]
    seeds: dict[str, list[object]] = {
        "pgns_schema": [{"run_id": f"{_OID}-3", "pgn_zip": pgn, "size": len(pgn)}],
        "user_schema": [{
            "username": "seeder", "password": "pw", "registration_time": _SEED_TIME,
            "pending": False, "blocked": False, "email": "seeder@example.org",
            "groups": ["approvers"], "tests_repo": "", "machine_limit": 8,
        }],
        "kvstore_schema": [{"_id": "seed", "value": {"nested": [1, 2]}}],
        "worker_schema": [{
            "worker_name": _SEED_SHORT_WORKER, "blocked": False, "message": "hi",
            "last_updated": _SEED_TIME,
        }],
        "nn_schema": [net, tested],
        "contributors_schema": [{
            "_id": _ObjectId(), "cpu_hours": 1.5, "diff": 0.0, "games": 10,
            "games_per_hour": 2.0, "last_updated": _SEED_TIME,
            "str_last_updated": "today", "tests": 1, "tests_repo": "",
            "username": "seeder",
        }],
        "action_schema": actions,
        "results_schema": [_SEED_RESULTS],
        "api_access_schema": [
            {"password": "pw", "worker_info": {"username": "seeder"}}
        ],
        "api_schema": [{
            "password": "pw", "run_id": _OID, "task_id": 3,
            "worker_info": _WORKER_INFO_API, "stats": _SEED_RESULTS,
        }],
        "runs_schema": [run],
        "worker_info_schema_api": [_WORKER_INFO_API],
        "worker_info_schema_runs": [_WORKER_INFO_RUNS],
    }  # fmt: skip
    return copy.deepcopy(seeds)


#: The mutations the conformance ledger's typed-singleton row parts, by schema,
#: path and kind: a finished run writes `0.0` for `nps` and `games_per_minute`,
#: which vtjson's `==` meets with the int `0` and valgebra's typed singleton does
#: not (docs/03-conformance.md, "Literal / constant equality").
_TYPED_SINGLETONS = {
    ("runs_schema", ("nps",), "int and float swapped"),
    ("runs_schema", ("games_per_minute",), "int and float swapped"),
}


def _paths(value: object, prefix: tuple = ()) -> list[tuple]:
    """Every path into ``value``, a list read at its first item."""
    found = [prefix]
    if isinstance(value, dict):
        for key in value:
            found += _paths(value[key], (*prefix, key))
    elif isinstance(value, list) and value:
        found += _paths(value[0], (*prefix, 0))
    return found


def _at(document: object, path: tuple) -> object:
    for step in path:
        document = document[step]  # ty: ignore[not-subscriptable]
    return document


def _mutations(document: object) -> list[tuple[tuple, str, object]]:
    """Each mutation of ``document``, as its path, its kind and the document.

    A key added to every mapping; at every path, the key deleted and the value
    replaced by one of another kind -- `None`, a string, `-1`, `True` -- and a
    number by the other kind of number, NaN and infinity.
    """
    found = []
    for path in _paths(document):
        node = _at(document, path)
        if isinstance(node, dict):
            added = copy.deepcopy(document)
            _at(added, path)["zz_added"] = 1  # ty: ignore[invalid-assignment]
            found.append((path, "key added", added))
        if not path:
            continue
        parent, last = path[:-1], path[-1]
        if isinstance(_at(document, parent), dict):
            deleted = copy.deepcopy(document)
            del _at(deleted, parent)[last]  # ty: ignore[not-subscriptable]
            found.append((path, "key deleted", deleted))
        kinds: dict[str, object] = {
            "None": None,
            "a string": "zz",
            "-1": -1,
            "True": True,
        }
        if isinstance(node, int) and not isinstance(node, bool):
            kinds.update(
                {
                    "int and float swapped": float(node),
                    "NaN": math.nan,
                    "infinity": math.inf,
                }
            )
        elif isinstance(node, float):
            kinds.update(
                {
                    "int and float swapped": int(node),
                    "NaN": math.nan,
                    "infinity": math.inf,
                }
            )
        for kind, value in kinds.items():
            if type(value) is type(node) and value == node:
                continue
            changed = copy.deepcopy(document)
            _at(changed, parent)[last] = value  # ty: ignore[invalid-assignment]
            found.append((path, kind, changed))
    return found


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


def test_fishtest_seeds_and_their_mutations_reach_vtjsons_decision() -> None:
    """Each string-keyed schema accepts its seeds, and their mutations agree.

    Every seed is accepted by both engines, so every schema's accept path is read;
    every mutation of a seed reaches vtjson's decision, but the ledger's
    typed-singleton rows, which are asserted the way the ledger states them:
    vtjson accepts and valgebra refuses.
    """
    source = _fetch_source()
    if source is None:
        pytest.skip("the fishtest schema source is not reachable (offline)")
    try:
        vt_schemas = _build(vt, source)
        vg_schemas = _build(vg, source)
    except ImportError as exc:  # an optional format extra is not installed
        pytest.skip(f"optional dependency missing: {exc}")

    seeds = _seeds()
    assert set(seeds) == set(_STRING_KEYED)
    singletons = set()
    for name, documents in seeds.items():
        vt_schema, vg_schema = vt_schemas[name], vg_schemas[name]
        for document in documents:
            assert _accepts(vt.validate, vt_schema, document), (name, document)
            assert _accepts(vg.validate, vg_schema, document), (name, document)
            for path, kind, mutated in _mutations(document):
                vt_ok = _accepts(vt.validate, vt_schema, mutated)
                vg_ok = _accepts(vg.validate, vg_schema, mutated)
                if (name, path, kind) in _TYPED_SINGLETONS:
                    singletons.add((name, path, kind))
                    assert (vt_ok, vg_ok) == (True, False), (name, path, kind)
                else:
                    assert vt_ok == vg_ok, (
                        f"{name} {path} {kind}: vtjson={vt_ok} compat={vg_ok}"
                    )
    assert singletons == _TYPED_SINGLETONS


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


class UpstreamMovedWarning(UserWarning):
    """fishtest's master holds another ``schemas.py`` than the pinned commit's."""


def test_the_pin_is_read_against_upstream() -> None:
    """Warn, never fail, where fishtest's master has moved past the pin.

    A moved file is no failure of this layer: the pin is what the conformance
    claim reads. The warning names the commit that last touched the file, the
    one to read and pin next, so the pin does not age unread.
    """
    pinned, master = _fetched(_URL), _fetched(_MASTER_URL)
    if pinned is None or master is None:
        pytest.skip("the fishtest schema source is not reachable (offline)")
    if master == pinned:
        return
    history = _fetched(_HISTORY_URL)
    try:
        latest = json.loads(history)[0]["sha"] if history else None
    except (ValueError, LookupError, TypeError):
        latest = None
    warnings.warn(
        UpstreamMovedWarning(
            f"fishtest's master holds another schemas.py than {_COMMIT[:12]}; "
            f"read {latest[:12] if latest else 'its history'} and pin it next"
        ),
        stacklevel=1,
    )


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
