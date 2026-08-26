# CLAUDE

See [AGENTS.md](AGENTS.md). It is the single set of instructions for this
repository — contract, setup, gate, layout, project rules, and commit format.

Two things are worth knowing before the first edit:

- **One-to-one with vtjson is the contract.** A difference is a defect until it
  is in [docs/03-conformance.md](docs/03-conformance.md) with a reason.
- **A change that classifies a schema must be run on the oldest supported
  interpreter**, not just the newest. The typing runtime answers differently
  across them, and the local gate hides it. See
  [docs/04-interpreters.md](docs/04-interpreters.md).
