# valgebra-vtjson

A vtjson interoperability layer for [valgebra](https://github.com/ppigazzini/valgebra).

valgebra is a standalone validation library with its own Boolean schema algebra.
This package is a separate, optional layer that reads
[vtjson](https://pypi.org/project/vtjson/)-style schemas and validates them
through valgebra, reaching the same accept/reject decision — proven by a
differential suite run against pinned upstream vtjson.

It doubles as a real-world conformance harness for valgebra: the test suite runs
actual project schemas — including [fishtest](https://github.com/official-stockfish/fishtest)'s,
fetched at a pinned commit and never vendored — through both vtjson and valgebra
and asserts they agree. That's evidence valgebra's core can express the schemas a
real codebase depends on, not just synthetic examples.

Keeping the layer in its own repo also keeps valgebra's own surface free of
vtjson: interop is a downstream concern, with its own tests and dependencies.

## Install

valgebra-vtjson is not on PyPI; install it from the Git repository. valgebra
itself resolves from PyPI as a normal dependency.

```bash
pip install "valgebra-vtjson @ git+https://github.com/ppigazzini/valgebra-vtjson"
# optional network/format validators:
pip install "valgebra-vtjson[formats] @ git+https://github.com/ppigazzini/valgebra-vtjson"   # email, domain_name
pip install "valgebra-vtjson[magic] @ git+https://github.com/ppigazzini/valgebra-vtjson"     # magic (needs system libmagic)
```

## Use

```python
import vtjson_compat as vtjson

schema = {"name": str, "age?": int}
vtjson.validate(schema, {"name": "Ada", "age": 36})  # passes
```

The compatibility surface mirrors vtjson's names. See
[docs/vtjson-conformance.md](docs/vtjson-conformance.md) for the full
mapping and the ledger of intentional behavioral differences.

> This layer is a supported, tested way to run existing vtjson schemas on
> valgebra, for as long as you need it. For *new* schemas, valgebra's native API
> is usually the more direct expression.

## Conformance

The layer is proven against real schemas, not just examples. A differential
suite feeds the same values to pinned upstream vtjson and to valgebra and
asserts they reach the same accept/reject decision, so any drift fails a test.

The headline corpus is [fishtest](https://github.com/official-stockfish/fishtest)'s
own schemas — fetched at a pinned commit and never vendored (they carry no
license). Every string-keyed schema, including the full run document
(`runs_schema`), `api_schema`, `action_schema`, and `results_schema`, and all
six schema-keyed tables, reach identical decisions through both engines. A
parity-inventory test also classifies every name on vtjson's public surface as
supported, ledgered, or infrastructure, so a future vtjson release cannot add a
construct that silently goes unsupported.

That makes this repo valgebra's real-world proving ground: if the core can carry
fishtest's schemas with exact parity, it can carry a real codebase's. The
construct mapping and the full ledger of intentional differences are in
[docs/vtjson-conformance.md](docs/vtjson-conformance.md).

## Performance

Translating a vtjson schema onto valgebra's Rust core makes the same schema
validate much faster than under pure-Python vtjson, with the same accept/reject
decision. On a synthetic benchmark (compile-once on both sides, against the
LTO+PGO release wheel of valgebra), valgebra is ~14x faster on a 50-field record
and ~21x–29x faster on nested records, deep nesting, large arrays, and unions.
Numbers, method, and limits are in
[docs/performance.md](docs/performance.md).

## Development

`uv sync` installs `valgebra` from PyPI alongside the dev tooling:

```bash
uv sync
uv run pytest
uv run ruff check
uv run ty check
```

The fishtest upstream conformance test fetches its schema at run time (the
schema is unlicensed and never vendored) and skips when offline.

## License

MIT OR Apache-2.0, matching valgebra.
