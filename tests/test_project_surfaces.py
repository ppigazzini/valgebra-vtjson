"""The surfaces around the code, held to the same standard as the code.

Every defect this suite has closed was reachable because something outside the
Python was wrong: an oracle pinned only by a floor, a lane that ran one
interpreter for five claimed, a construct list nobody owned, and prose that
described a defect as a decision. None of it is checkable by a type checker or
a differential row, so it is checked here.

Each assertion reads the tree rather than restating it, so a surface that moves
fails this file instead of drifting quietly away from what the project claims.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - only on the oldest supported interpreter
    import tomli as tomllib
from pathlib import Path

import pytest
import valgebra
import vtjson as vt

from vtjson_compat import _valgebra_api

_ROOT = Path(__file__).resolve().parent.parent
_CONFIG = tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
_CI = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

# Words that date a page. A shipped page states what is true; the before and
# after belongs in the commit message, which is the durable per-task record.
_DATED = re.compile(
    r"\b(now|no longer|were once|has since|used to|previously|will be)\b",
    re.IGNORECASE,
)


def _shipped_prose() -> list[Path]:
    """Return every Markdown page the project publishes."""
    return [*sorted((_ROOT / "docs").glob("*.md")), _ROOT / "README.md"]


def _tracked() -> set[str]:
    """Return every path git tracks."""
    listing = subprocess.run(  # noqa: S603
        ["git", "-C", str(_ROOT), "ls-files"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return set(listing.stdout.split())


def test_the_oracle_is_pinned_not_floored() -> None:
    """A conformance claim is reproducible only against one oracle version."""
    requirements = [
        requirement
        for group in _CONFIG["dependency-groups"].values()
        for requirement in group
        if requirement.startswith("vtjson")
    ]
    assert requirements, "vtjson is not in any dependency group"
    for requirement in requirements:
        assert "==" in requirement, (
            f"the oracle is pinned by a floor, not a version: {requirement}"
        )
    pinned = requirements[0].split("==")[1].strip('"')
    assert vt.__version__ == pinned, (
        f"pyproject pins vtjson {pinned}, the environment has {vt.__version__}"
    )


def test_the_resolution_is_tracked() -> None:
    """The lock is what makes the pinned oracle reach a clean clone."""
    assert "uv.lock" in _tracked(), "uv.lock is not tracked, so CI resolves afresh"


def test_the_lane_uses_the_locked_resolution() -> None:
    """A lane that re-resolves is not running the versions the tree records."""
    assert "--locked" in _CI, "CI syncs without --locked"


def test_every_claimed_interpreter_is_tested() -> None:
    """A version in the classifiers is a promise the lane has to keep."""
    claimed = {
        classifier.rsplit(" ", 1)[1]
        for classifier in _CONFIG["project"]["classifiers"]
        if classifier.startswith("Programming Language :: Python :: 3.")
    }
    untested = sorted(version for version in claimed if version not in _CI)
    assert not untested, f"claimed but absent from the CI matrix: {untested}"


def test_the_lane_measures_coverage() -> None:
    """A suite whose reach nobody measures is a suite whose gaps nobody sees."""
    assert "--cov" in _CI, "CI runs no coverage gate"


@pytest.mark.parametrize("page", _shipped_prose(), ids=lambda p: p.name)
def test_a_page_states_what_is_true_rather_than_what_changed(page: Path) -> None:
    """Shipped prose carries no history."""
    dated = [
        f"{page.name}:{number}: {line.strip()}"
        for number, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1)
        if _DATED.search(line)
    ]
    assert not dated, "\n".join(dated)


def test_the_construct_inventory_has_one_owner() -> None:
    """A list written twice is a list that disagrees with itself.

    `tests/test_parity_inventory.py` holds the layer to vtjson's surface name by
    name. A second copy in prose cannot be checked against anything, and reads
    exactly the same whether it is current or a release out of date.
    """
    owner = _ROOT / "tests" / "test_parity_inventory.py"
    marker = "at_least_one_of"
    prose = {
        page.relative_to(_ROOT): page.read_text(encoding="utf-8")
        for page in _shipped_prose()
    }
    # The package's own `import` and `__all__` are the export list, not a
    # restatement of it, so only the module docstring counts as prose here.
    package = _ROOT / "vtjson_compat" / "__init__.py"
    docstring = ast.get_docstring(ast.parse(package.read_text(encoding="utf-8"))) or ""
    prose[package.relative_to(_ROOT)] = docstring

    copies = sorted(str(path) for path, text in prose.items() if marker in text)
    assert not copies, (
        f"the construct inventory is restated in {copies}; "
        f"{owner.relative_to(_ROOT)} owns it"
    )


def test_the_error_type_is_classified_as_supported() -> None:
    """`SchemaError` is a construct of the surface, not internal machinery.

    Filing it as infrastructure is what excused the layer from raising it at
    all: the inventory asks nothing further of a name in that bucket.
    """
    inventory = (_ROOT / "tests" / "test_parity_inventory.py").read_text(
        encoding="utf-8"
    )
    supported = inventory.partition("_LEDGERED")[0]
    assert '"SchemaError"' in supported, (
        "SchemaError is not classified as supported, so nothing holds the layer "
        "to raising it"
    )


def test_the_distribution_carries_a_version_and_a_changelog() -> None:
    """A layer people install is one they can tell the versions of apart."""
    assert _CONFIG["project"]["version"] != "0.0.0", "the version is still the default"
    assert (_ROOT / "CHANGELOG.md").is_file(), "no changelog"


def test_the_layer_builds_on_valgebra_s_public_surface() -> None:
    """Only names `valgebra.__all__` exports are imported.

    `valgebra._valgebra` is the extension module, not the package: what it
    exports is an implementation detail that can be renamed in a release that
    promises nothing about it. Everything the layer needs is public, so reaching
    past the package buys a coupling and nothing else.
    """
    # An import, not a mention: naming the module in prose to say why it is
    # avoided is the point of the docstring that does so.
    reaches_past = re.compile(r"^\s*(from|import)\s+valgebra\._valgebra\b")
    private = sorted(
        f"{path.relative_to(_ROOT)}:{number}"
        for path in sorted((_ROOT / "vtjson_compat").glob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if reaches_past.match(line)
    )
    assert not private, "imports from the extension module: " + ", ".join(private)


def test_every_valgebra_name_the_layer_takes_is_public() -> None:
    """Guard the guard: the check above is only meaningful if the names exist."""
    taken = {
        name
        for name in dir(_valgebra_api)
        if not name.startswith("_") and name in dir(valgebra)
    }
    assert taken, "no valgebra names found in the adapter; the check is stale"
    assert taken <= set(valgebra.__all__), sorted(taken - set(valgebra.__all__))


# The builtins that are generic: written bare, each says "a container of
# something" and the something is exactly what a reader needs.
_GENERIC = frozenset({"dict", "list", "set", "tuple", "frozenset"})


def _bare_generics(tree: ast.AST) -> list[str]:
    """Return every annotation naming a generic without its parameters."""
    found: list[str] = []

    def visit(node: ast.AST | None) -> None:
        match node:
            case ast.Name(id=name) if name in _GENERIC:
                found.append(f"{name} at line {node.lineno}")
            case ast.BinOp(left=left, right=right):  # `dict | None`
                visit(left)
                visit(right)
            case _:
                return

    for node in ast.walk(tree):
        match node:
            case ast.FunctionDef(args=args, returns=returns):
                for argument in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                    visit(argument.annotation)
                visit(args.vararg.annotation if args.vararg else None)
                visit(args.kwarg.annotation if args.kwarg else None)
                visit(returns)
            case ast.AnnAssign(annotation=annotation):
                visit(annotation)
    return found


def test_no_annotation_names_a_generic_without_its_parameters() -> None:
    """A container annotation says what it contains.

    `dict` alone carries no more than the name of the call it appears in. The
    type checker accepts it, so nothing else objects; the reader is the one who
    pays, and so is the next person who has to guess what belongs in it.
    """
    bare = {
        str(path.relative_to(_ROOT)): found
        for path in sorted((_ROOT / "vtjson_compat").glob("*.py"))
        if (found := _bare_generics(ast.parse(path.read_text(encoding="utf-8"))))
    }
    assert not bare, f"unparameterised annotations: {bare}"
