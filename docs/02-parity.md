# Parity

What "one-to-one with vtjson" means, how it is proven, and where a difference is
allowed to live.

## The contract

For every vtjson construct and every value, this layer reaches the **same
accept/reject decision as vtjson** — except at the points recorded in
[03-conformance.md](03-conformance.md).

A difference not in that ledger is a defect. Not a design, not a simplification,
not an improvement: a defect, with a test row missing.

## The oracle

vtjson is a pinned dev dependency, and the differential suite runs the real
package beside this one. Pinning is what makes a divergence attributable: an
unpinned oracle turns a vtjson release into a mystery failure here.

The oracle is never vendored, and neither is any corpus. The fishtest schemas
are fetched at a pinned commit at run time and skip when offline; they carry no
license.

## Do not improve on the oracle

This is the rule that gets broken by good intentions.

vtjson has shapes that are degenerate. A `frozenset` schema requires the value to
be both a `frozenset` and a `set`, which nothing satisfies, so it is uninhabited.
`type[int]` admits nothing on one interpreter and everything on the next.
Matching those is what a one-to-one layer owes.

Diverging in the direction of "more useful" is how a compatibility layer stops
being one — and it destroys the thing this repo is for. A layer that quietly
corrects its oracle cannot tell you which of the two implementations is
wrong, which is the whole value of running them side by side.

If a difference is genuinely wanted, it goes in the ledger with its reason
**before** the code lands.

## What the ledger is for

[03-conformance.md](03-conformance.md) holds every intentional
difference. An entry says what differs, in which direction, and why matching
would cost more than it is worth.

An entry that says "not worth it" carries a price estimate, and an estimate made
while the machinery was different is worth re-reading when the machinery
changes. Entries resting on a *reason* — matching would mean crashing on
purpose — survive that re-reading. Entries resting on an *estimate* of
implementation cost should be re-priced whenever a new mechanism lands, because
one of them has already turned out to be wrong about its own price.

## Two directions, and one is worse

When the layer and vtjson disagree about an exception rather than a verdict,
the direction matters:

- **vtjson lets an exception out, the layer rejects.** A value that breaks a leaf
  is not a member; this layer answers where vtjson crashes. Ledgered.
- **The layer raises where vtjson decides.** Strictly worse, and never
  acceptable. A caller who asked a yes/no question cannot catch a
  `NotImplementedError` as an answer. If valgebra builds no node for the form,
  the layer still has to decide.

## When valgebra is the one that is wrong

Some divergences found here have been valgebra's. That is the harness working,
and the response is to fix it there — with the set of values that needs
denoting — rather than to paper over it with a predicate.

The layer's floor on valgebra moves when such a fix ships; until then the
divergence is a ledger row like any other, and the tree here does not change.
