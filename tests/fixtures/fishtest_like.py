"""A fishtest-representative schema and document corpus for differential parity.

fishtest validates MongoDB run documents with vtjson, using union, intersect,
ge/gt, regex, ip_address, keys/one_of, size, lax, set_name, and friends. The
live fishtest schemas additionally use ``magic`` (file content), ``ObjectId``
predicates (pymongo), and ``set_label``/``subs`` recursion, which are recorded
in the differences ledger rather than reproduced here.

``build`` takes a schema library module (the real ``vtjson`` or
``vtjson_compat``) and constructs the same schema with it, so one
definition drives both sides of the differential test.
"""

from typing import Any


def build(lib: Any) -> object:
    """Build a fishtest-like run-document schema using ``lib``'s constructs."""
    worker = {
        "worker_name": lib.regex(r"[A-Za-z0-9_.-]+"),
        "ip?": lib.ip_address(),
        "concurrency": lib.intersect(int, lib.ge(1)),
        "last_seen?": lib.date_time(),
    }
    args = {
        "num_games": lib.intersect(int, lib.ge(0)),
        "tc": lib.regex(r"\d+(\.\d+)?\+\d+(\.\d+)?"),
        "book": str,
        "threads?": lib.intersect(int, lib.ge(1)),
        "info?": str,
    }
    results = {"wins": int, "losses": int, "draws": int}
    return {
        "run_id": lib.regex(r"[0-9a-f]{24}"),
        "args": args,
        "results": results,
        "workers": [worker, ...],
        "state": lib.union("pending", "active", "finished"),
        # at least one of these throughput knobs must be present
        "config": lib.intersect(
            lib.lax({"priority?": int}),
            lib.at_least_one_of("priority", "throughput"),
        ),
        "tags?": lib.intersect([str, ...], lib.unique()),
    }


def _run(*, ip: str = "1.2.3.4", workers: bool = True) -> dict:
    crew = [{"worker_name": "w-1", "ip": ip, "concurrency": 4}] if workers else []
    return {
        "run_id": "0123456789abcdef01234567",
        "args": {"num_games": 100, "tc": "10+0.1", "book": "x.epd"},
        "results": {"wins": 1, "losses": 2, "draws": 3},
        "workers": crew,
        "state": "active",
        "config": {"priority": 1, "extra": "ok"},  # lax: extra key allowed
        "tags": ["a", "b"],
    }


# (document, expected accept/reject). Both libraries must agree, and must agree
# with `expected`, so the corpus stays meaningful.
def cases() -> list[tuple[dict, bool]]:
    good = _run()

    bad_run_id = _run()
    bad_run_id["run_id"] = "not-an-id"

    bad_state = _run()
    bad_state["state"] = "paused"

    bad_ip = _run(ip="999.1.1.1")

    bad_results = _run()
    bad_results["results"]["wins"] = "many"

    missing_config_knob = _run()
    missing_config_knob["config"] = {}  # neither priority nor throughput

    dup_tags = _run()
    dup_tags["tags"] = ["a", "a"]

    throughput_only = _run()
    throughput_only["config"] = {"throughput": 50}

    return [
        (good, True),
        (throughput_only, True),
        (bad_run_id, False),
        (bad_state, False),
        (bad_ip, False),
        (bad_results, False),
        (missing_config_knob, False),
        (dup_tags, False),
    ]
