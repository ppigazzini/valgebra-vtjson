"""Every name the layer points a reader at is a name that exists.

Prose and error messages send people somewhere. A docstring naming a valgebra
API that was never called that, or an ``ImportError`` naming the wrong extra,
costs a reader the time it takes to discover the instruction was impossible —
and neither the type checker nor the differential suite can see it, because
nothing about the layer's behaviour is wrong.

Both checks are driven from the tree rather than from a list written here: the
valgebra names come out of `valgebra.__all__`, and the extras come out of
``pyproject.toml``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - only on the oldest supported interpreter
    import tomli as tomllib
import valgebra

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Iterator

_ROOT = Path(__file__).resolve().parent.parent

# A code span the prose attributes to valgebra: "valgebra's ``x``", or "``x``
# fixpoint". Both spellings of code span are matched, since the docstrings use
# reStructuredText and the pages use Markdown.
_CLAIMED = re.compile(r"valgebra's ``?(\w+)``?|``?(\w+)``? fixpoint")


def _prose_files() -> Iterator[Path]:
    """Yield every shipped file whose prose can name a valgebra API."""
    yield from sorted((_ROOT / "vtjson_compat").glob("*.py"))
    yield from sorted((_ROOT / "docs").glob("*.md"))
    yield _ROOT / "README.md"


def _claims() -> list[tuple[Path, str]]:
    """Return every valgebra name the shipped prose attributes to valgebra."""
    found: list[tuple[Path, str]] = []
    for path in _prose_files():
        for match in _CLAIMED.finditer(path.read_text(encoding="utf-8")):
            name = match.group(1) or match.group(2)
            found.append((path.relative_to(_ROOT), name))
    return found


def test_the_prose_names_at_least_one_valgebra_api() -> None:
    """Guard the guard: a regex that matches nothing would pass silently."""
    assert _claims(), "no valgebra API names found in the prose; the pattern is stale"


def test_every_valgebra_name_in_the_prose_exists() -> None:
    """A valgebra API the prose names is one a reader can import and call."""
    missing = [
        f"{path}: valgebra has no {name!r}"
        for path, name in _claims()
        if not hasattr(valgebra, name)
    ]
    assert not missing, "\n".join(missing)


def test_the_unsupported_recursion_message_names_a_real_fixpoint() -> None:
    """The way out an error offers is one the reader can actually take."""
    with pytest.raises(NotImplementedError) as raised:
        vg.validate({"a": int}, {"a": 1}, subs={"x": str})
    words = set(re.findall(r"\w+", str(raised.value)))
    assert words & set(valgebra.__all__), (
        f"the message names no valgebra API: {raised.value}"
    )


def _extras() -> dict[str, str]:
    """Map each optional distribution to the extra that installs it."""
    config = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    optional = config["project"]["optional-dependencies"]
    return {
        re.split(r"[<>=!\[]", requirement)[0].strip(): extra
        for extra, requirements in optional.items()
        for requirement in requirements
    }


# The import each construct needs, and the distribution that provides it. The
# extra itself is never written here — it is read from pyproject.toml, so a
# construct moved between extras fails this test rather than misleading a user.
OPTIONAL: list[tuple[str, str, str]] = [
    ("email", "email_validator", "email-validator"),
    ("domain_name", "idna", "idna"),
    ("magic", "magic", "python-magic"),
]


@pytest.mark.parametrize(
    ("construct", "module", "distribution"),
    OPTIONAL,
    ids=[row[0] for row in OPTIONAL],
)
def test_a_missing_extra_is_named_correctly(
    monkeypatch: pytest.MonkeyPatch,
    construct: str,
    module: str,
    distribution: str,
) -> None:
    """When an optional import fails, the error names the extra that supplies it."""
    extra = _extras()[distribution]
    # A `None` entry in sys.modules makes any import of that name raise, which
    # `importlib.import_module` honours where a patched `builtins.__import__`
    # would not: import_module does not route through it.
    monkeypatch.setitem(sys.modules, module, None)

    argument = ("image/png",) if construct == "magic" else ()
    with pytest.raises(ImportError) as raised:
        getattr(vg, construct)(*argument)
    assert f"[{extra}]" in str(raised.value), (
        f"{construct} needs the {extra!r} extra; the error says: {raised.value}"
    )
