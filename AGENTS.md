# AGENTS

valgebra-vtjson reads a [vtjson](https://pypi.org/project/vtjson/)-style schema
and validates it through [valgebra](https://github.com/ppigazzini/valgebra),
reaching the same accept/reject decision. It is a compatibility layer, and it is
also valgebra's real-world conformance harness: a second implementation driven
over the same inputs, disagreeing out loud.

The layer does not import vtjson. It reimplements vtjson's surface on top of
valgebra's algebra, and a differential suite runs the pinned real vtjson beside
it as an oracle.

**One-to-one with vtjson is the contract**, not an aspiration. A difference is a
defect until it is written into the ledger with a reason. Keep that framing in
code, docs, and commits.


## Read first

[docs/](docs/README.md) is the documentation set: one page per concern, each
the live claim about it. Read the page that owns what you are
changing, and fix that page in the same commit.

| Changing | Read |
|---|---|
| how the layer is put together | [docs/00-architecture.md](docs/00-architecture.md) |
| how a schema becomes a validator | [docs/01-translation.md](docs/01-translation.md) |
| what counts as a divergence | [docs/02-parity.md](docs/02-parity.md) |
| anything that classifies a schema | [docs/04-interpreters.md](docs/04-interpreters.md) |
| a test, a sweep, or a gate | [docs/05-testing.md](docs/05-testing.md) |
| any prose at all | [docs/07-writing.md](docs/07-writing.md) |

The user-facing ledger of intentional differences is
[docs/03-conformance.md](docs/03-conformance.md). It is the only place a
divergence is allowed to live.


## Setup

```bash
uv sync          # resolve and install dev dependencies into .venv
```

`uv` must be on PATH. valgebra resolves from PyPI as an ordinary dependency —
there is no Rust toolchain and nothing to build here.


## Build Health Gate

A change is not done until every command exits 0. Trust exit codes, not log
text — a process can print progress and then fail. If a gate cannot run, say so
and list what was checked instead.

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

**A change that touches how a schema is classified is not covered by that gate.**
Run the parity suite on the oldest supported interpreter as well:

```bash
uv sync --locked --python 3.10 && uv run --no-sync pytest
uv sync --locked --python 3.14 && uv run --no-sync pytest
```

Those two are the ends of the range. `requires-python` in `pyproject.toml` owns
the floor and `.github/workflows/ci.yml` owns the interpreters CI runs between
them; check both rather than trusting the pair above to still be the ends.
[docs/04-interpreters.md](docs/04-interpreters.md) says why it matters.


## Layout

- `vtjson_compat/_valgebra_api.py` — every valgebra name the package uses, under
  the name it uses. The only module that imports valgebra.
- `vtjson_compat/_translate.py` — the schema translator: classification,
  containers, strictness.
- `vtjson_compat/_constructs.py` — the vtjson combinators, refinements,
  modifiers, and wrappers.
- `vtjson_compat/_formats.py` — the string and network format validators.
- `vtjson_compat/__init__.py` — the public surface.
- `tests/` — pytest suites, differential against the pinned oracle.
- `benches/` — the comparison benchmarks behind `docs/06-performance.md`.

Style, naming, and formatting are enforced by ruff and ty — follow their output
rather than restating rules here.


## Project Rules

These are the invariants tooling cannot enforce. Each pairs a prohibition with
what to do instead.

- **Build it out of valgebra.** Every decision this layer makes must be a
  valgebra validator's decision. Reach for the algebra first — `union`,
  `intersection`, `complement`, the container and mapping nodes, refinements —
  and let valgebra decide. Do not hand-roll in Python what the algebra already
  denotes.

- **A predicate is the last resort, and it is opaque.** valgebra's documented
  Python-callback path is a black box to the algebra: it cannot be simplified,
  intersected, or explained, and it costs a call per value. Use one only where
  vtjson's meaning is genuinely dynamic, keep it as small as the dynamic part,
  and put a real node beside it for the part that is not. A container class the
  algebra cannot name is still an atom next to a narrow predicate, not one big
  predicate.

- **Import from `valgebra`, never from `valgebra._valgebra`.** What the
  extension module exports is an implementation detail; `valgebra.__all__` is
  the surface valgebra supports. Every name enters through
  `vtjson_compat/_valgebra_api.py` so the coupling is one file wide.

- **When valgebra cannot express something, that is a valgebra finding.** Say so
  and raise it there, with the set of values that needs denoting. Do not work
  around it here with a predicate and leave the hole unrecorded — the point of
  this repo is that the hole gets found.

- **A refusal is not a verdict.** If valgebra builds no node for a form vtjson
  decides, the layer must still decide. Letting `NotImplementedError` reach a
  caller who asked a yes/no question is worse than a wrong answer, because it
  cannot be caught as one.

- **Do not diverge in the direction of "more useful".** A schema that is
  uninhabited, degenerate, or interpreter-dependent in vtjson stays that way
  here. Improving on the oracle is how a compatibility layer stops being one.
  If a difference is genuinely wanted, it goes in the ledger with its reason
  before the code lands.

- **Prove the divergence before fixing it.** Write the parity row, run it red
  against the pinned oracle, then implement, then run it green. A fix without a
  red row is a guess that happens to pass.

- **Sweep a surface, not an example.** A rule applied to one shape and not to its
  neighbours is this layer's recurring defect. When you fix a shape, enumerate
  the shapes beside it and compare both columns against the oracle across the
  cross-product.

- **Check a construct's arguments when the schema is built.** Arguments that
  cannot denote a set raise `SchemaError`, as in vtjson — not a validator that
  quietly admits everything. `ValidationError` is for a value; `SchemaError` is
  for a schema.

- **Never vendor the oracle or a corpus.** vtjson is a pinned dev dependency.
  The fishtest schemas are fetched at a pinned commit and never copied into this
  tree; they carry no license.

- **Keep vtjson's spelling, argument names included.** The layer is a drop-in, so
  a call written by keyword against vtjson's documentation must run here
  unchanged — even where that shadows a builtin. Those suppressions are the
  price of the contract, not debt.


## Commits

Conventional commits, body wrapped at 80 columns. Describe the system as it
stands after the change in authoritative mood — not "added X" or "this commit".
No meta commentary. No trailers. No references to untracked files.

```
fix: short imperative summary

Authoritative body wrapped at 80 columns describing the system as it
stands, not the act of changing it.
```

Where a change closes a divergence, the body says which shapes were compared and
against what — that record is the commit's job, and it does not belong on a
shipped page.
