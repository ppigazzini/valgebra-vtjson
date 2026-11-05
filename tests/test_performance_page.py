"""The performance page is held to the benchmark that produces it.

A ratio in prose is a claim about a measurement someone else has to trust. Three
things make it checkable: the families the page reports are the shapes the
benchmark defines, every figure carries the spread it was measured with — a bare
number reads the same whether it was stable or noise — and the conditions the
page names are ones its own command can be confirmed to have met.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from benches.bench_vtjson_compare import LABELS, SHAPES

_ROOT = Path(__file__).resolve().parent.parent
_PAGE = (_ROOT / "docs" / "06-performance.md").read_text(encoding="utf-8")
_README = (_ROOT / "README.md").read_text(encoding="utf-8")


def test_the_page_reports_every_shape_the_benchmark_measures() -> None:
    """A family the benchmark covers and the page omits is a silent gap."""
    assert set(LABELS) == set(SHAPES), "every shape needs the name it is reported under"
    table = _PAGE[_PAGE.index("## Baseline") :]
    missing = sorted(label for label in LABELS.values() if label not in table)
    assert not missing, (
        f"benched but absent from the page: {missing}. The benchmark owns the "
        "list of families; the page must not carry a shorter one."
    )


def test_every_reported_figure_carries_its_spread() -> None:
    """A speedup with no spread cannot be told from one measured once."""
    table = _PAGE[_PAGE.index("## Baseline") : _PAGE.index("## Honest limits")]
    ratios = re.findall(r"\d+(?:\.\d+)?x", table)
    assert ratios, "the baseline table reports no ratio at all"
    spreads = re.findall(r"±", table)
    assert len(spreads) >= len(ratios), (
        f"the table reports {len(ratios)} ratios and {len(spreads)} spreads; "
        "each figure needs the variation it was measured with"
    )


def test_the_page_states_how_the_numbers_were_produced() -> None:
    """A performance claim ships with what produced it."""
    for marker in ("## Method", "bench_vtjson_compare.py", "compile"):
        assert marker in _PAGE, f"docs/06-performance.md does not state {marker!r}"


def test_the_page_says_how_to_confirm_the_interpreter_build() -> None:
    """A condition the method cannot be checked against is not a method.

    The page reports figures from a GIL build and says so, because a
    free-threaded interpreter runs this work slower and by different factors for
    the two libraries. But `--python 3.14` resolves to whichever 3.14 is
    installed, which on a machine carrying a free-threaded one is that — so the
    command alone does not establish the condition the page claims.
    """
    assert "Py_GIL_DISABLED" in _PAGE, (
        "docs/06-performance.md reports a GIL build but gives no way to confirm "
        "one: `--python 3.14` resolves to whatever 3.14 is installed"
    )


def _newest_claimed() -> str:
    """Return the newest release the classifiers claim, as `3.15`."""
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    prefix = "Programming Language :: Python :: 3."
    minors = [
        int(classifier.removeprefix(prefix))
        for classifier in config["project"]["classifiers"]
        if classifier.startswith(prefix)
    ]
    return f"3.{max(minors)}"


def test_every_figure_is_measured_on_the_newest_interpreter_claimed() -> None:
    """A release the project claims and the page does not read goes unmeasured.

    Readings on two interpreters do not compare: one wheel reads a family slower
    on one release and faster on the next. So the page's interpreter, the command
    that reproduces it, and the lane that smoke-runs the benchmark all name the
    newest release, and claiming a newer one fails here until they follow it.
    """
    newest = _newest_claimed()
    baseline = _PAGE[_PAGE.index("## Baseline") : _PAGE.index("## Honest limits")]
    assert re.search(rf"CPython {re.escape(newest)}\.\d+ standard build", baseline), (
        f"docs/06-performance.md does not report CPython {newest}"
    )
    assert f"--python {newest}" in _PAGE, f"the page's command does not name {newest}"
    lane = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    checks = lane[lane.index("  checks:") :]
    assert f'python-version: "{newest}"' in checks, (
        f"the lane smoke-running the benchmark does not read {newest}"
    )


def test_only_the_page_quotes_a_ratio() -> None:
    """A figure repeated somewhere else is a second copy to drift from.

    The benchmark owns these numbers and the page reports them with the spread
    and the limits they were measured under. A ratio quoted in the README
    carries neither, and a reader has no way to tell that the families it names
    are the flattering ones.
    """
    quoted = re.findall(r"\d+(?:\.\d+)?x", _README)
    assert not quoted, (
        f"README.md quotes {quoted}; docs/06-performance.md owns the ratios, "
        "with the spread and the limits each was measured under"
    )
