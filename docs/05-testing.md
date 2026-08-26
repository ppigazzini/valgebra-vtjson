# Testing

How a claim about parity gets proven here, and what the gate cannot see.

## Red first, against the oracle

A fix without a failing row is a guess that happens to pass. The order is:

1. Write the parity row — the schema, the values, both columns.
2. Run it and watch it fail, with the divergence printed.
3. Implement.
4. Run it and watch it pass.

Step 2 is the one that gets skipped, and skipping it is how a test that asserts
nothing lands green. A row that was never red proves only that it agrees with
whatever the code already did.

## Both columns come from one builder

A parity row builds its schema **once per library** from the same argument tuple:

```python
ROWS = [("Annotated[int, ge(0)]", lambda m: Annotated[int, m.ge(0)], [1, 0, -1])]
reference, layer = build(vt), build(vg)
```

Passing `m` and calling it twice is what stops a row from silently comparing two
different schemas. A row that hard-codes each side separately can drift into
testing nothing, and it will still be green.

## Sweep a surface, not an example

The recurring defect in this layer is **a rule applied to one shape and not to
its neighbours** — laxness reaching dicts but not sequences, then not
`TypedDict`s, then not through generic aliases. An example tests the shape you
thought of.

So a sweep enumerates a surface and compares the cross-product against the
oracle: every schema form against every value kind, both columns, divergences
collected rather than asserted one at a time. `tests/` owns the list of surfaces
that have been swept — each is a module, and its docstring says which surface
and which axis. A list written here would be a second copy, and the last one
went stale within three commits.

Two things that sweep method taught, both worth keeping:

- **"No divergence" means the dimension is exhausted, not that the work is
  done.** The next dimension is usually not another kind of schema.
- **Choosing the surface is the part no sweep does.** One of these dimensions was
  chosen by a CI failure rather than by anyone's plan.

## A surface is not swept; an axis through it is

The sharper version, and the one that has found the most: a surface swept along
one axis says nothing about the next axis through it. Classes were swept by what
they *declare* and came back clean, then produced four defects when swept by
what *kind* of class they are. Combinators were swept by what they are *given*,
then produced ten when swept by *strictness*.

So a sweep is recorded with its axis, not just its surface, and each axis that
has been run lives in a module named after it. An axis verified once by hand is
verified once; an axis with a module is verified on every commit and every
interpreter in the matrix.

Three axes have turned out to be two axes wearing one name — classes by what
they *declare* against classes by what *kind* they are, combinators by their
*arguments* against combinators by *strictness*, interpreters by *version*
against interpreters by *build*. Each time, the sweep varied the obvious half
and the other half went unasked, so a module's docstring names its axis rather
than its surface.

**Write the axis down even when it finds nothing.** A clean axis is the record
that the question was asked, and the value of that record is what tells the next
reader which questions have *not* been.

## The gate

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run ty check
```

`.github/workflows/ci.yml` owns what CI runs, including the interpreter matrix.

## What the gate cannot see

- **A wrong answer both libraries agree on.** The oracle is vtjson, so a defect
  vtjson shares is invisible here by construction. Only reading the typing spec
  finds those.
- **A shape nobody wrote a row for.** Coverage is a statement about lines
  executed, not about schema forms enumerated. Every defect this layer has had
  was in code the suite already executed.
- **A behaviour that differs only on an interpreter the local run skips.** See
  [04-interpreters.md](04-interpreters.md) — including the *build*, since a
  version and a build are not the same interpreter.

## The inventory, so the surface cannot drift

A test classifies every name on vtjson's public surface as supported, ledgered,
or not-a-construct, and fails on a name it cannot place. That is what stops a
vtjson release from adding a construct that silently goes unsupported — a list
written into a page would not have caught it, because a page is not run.
