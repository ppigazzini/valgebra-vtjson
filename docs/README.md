# Documentation

One page per concern, each the live claim about it.

| Page | Covers |
|---|---|
| [00-architecture.md](00-architecture.md) | what the layer is made of, and where valgebra enters |
| [01-translation.md](01-translation.md) | how a vtjson schema becomes a valgebra validator |
| [02-parity.md](02-parity.md) | the one-to-one contract, the oracle, and the ledger |
| [03-conformance.md](03-conformance.md) | the construct mapping and every intentional difference |
| [04-interpreters.md](04-interpreters.md) | the typing runtime changes under the layer |
| [05-testing.md](05-testing.md) | sweeps, the red-first rule, and what the gate cannot see |
| [06-performance.md](06-performance.md) | what the Rust core buys, measured, with the method |
| [07-writing.md](07-writing.md) | the rules governing this prose |

[03-conformance.md](03-conformance.md) and [06-performance.md](06-performance.md)
answer a reader using the layer; the rest answer one changing it.

## Hot and cold

A page is **hot** when it describes code that moves, **cold** when what it
describes barely does. Change hot code, fix its page in the same commit.

| Page | Temperature |
|---|---|
| [00-architecture.md](00-architecture.md) | warm — the module boundary moves rarely |
| [01-translation.md](01-translation.md) | hot — every classification change lands here |
| [02-parity.md](02-parity.md) | warm — the contract is fixed, the ledger is not |
| [03-conformance.md](03-conformance.md) | hot — a closed divergence is a row removed |
| [04-interpreters.md](04-interpreters.md) | warm — a new interpreter adds a row |
| [05-testing.md](05-testing.md) | warm |
| [06-performance.md](06-performance.md) | warm — a number holds until the wheel or the method changes |
| [07-writing.md](07-writing.md) | cold |
