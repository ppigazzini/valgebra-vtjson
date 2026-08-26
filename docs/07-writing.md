# Writing rules

These govern the shipped prose — this set, `README.md`, `AGENTS.md`,
`CLAUDE.md`, the pages under `docs/` — and the comments in the source.

**valgebra's [writing rules](https://github.com/ppigazzini/valgebra/blob/main/docs/dev/12-writing.md)
apply here unchanged.** State the page contract first; say what a schema means as
a set of values; separate a verified fact from a decision; describe a gap as a
gap; verify the claim against the tree; never pin a number or a list that a gate
owns; state the limit; show the command; no history in shipped prose; pair every
prohibition with an alternative; cut anything that does not help implement or
verify.

What follows is what this repository adds.

## Two surfaces, and they must not converge

A second surface is untracked: the maintainer's planning notes, audit reports,
and analyses. A shipped page must not carry campaign history, and an untracked
note must not be the only place a shipped fact lives.

**A shipped file must not name that surface's location.** It is gitignored, so
the reference dangles for every reader but its author.

The practical consequence: when an audit finds something, the *finding* belongs
in the ledger or a page here, the *evidence* belongs in the commit message, and
the narrative stays where it was written.

## Say which library decides

Every sentence about behaviour is about one of three things, and blurring them
is this repository's characteristic prose defect:

- what **vtjson** does — checkable against the pinned oracle;
- what **valgebra** does — checkable against its docs and its tree;
- what **this layer** does to make the first two agree.

"The schema admits an int" is useless. "vtjson's `float` admits ints, so the
layer translates it to `union(int, float)`" says who decided what, and a reader
can check each half.

## A divergence is stated once

The ledger is the only place a difference lives. A page that re-explains a
ledgered divergence gives it a second copy to drift from, and the two will
disagree within a release. Link the ledger instead.

## No commit hashes, no milestone numbers

They are the untracked surface's vocabulary and they mean nothing to a reader
with a checkout. A page states what is true; the commit message carries the
before-and-after.

## Code comments

valgebra's comment rules apply: imperative mood, write only the constraint the
code cannot show, name the invariant and what breaks without it, no history and
no meta.

One addition, and it is the important one here. **A comment that explains a
translation says what vtjson means, not just what the code does.** The code shows
that a bare `float` becomes `union(int, float)`; only the comment can say that
vtjson's `float` admits ints, which is why. Without that sentence the next reader
cannot tell a deliberate translation from a bug.
