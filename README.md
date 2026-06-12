# valgebra-vtjson

A vtjson interoperability layer for [valgebra](https://github.com/ppigazzini/valgebra).

valgebra is a standalone validation library with its own Boolean schema algebra.
This package is a separate, optional layer for projects migrating off
[vtjson](https://pypi.org/project/vtjson/): it reads vtjson-style schemas and
validates them through valgebra, reaching the same accept/reject decision —
proven by a differential suite run against pinned upstream vtjson.

It exists so valgebra's own surface stays free of vtjson: interop is a
downstream concern, kept in its own repo with its own tests and dependencies.

## Install

```bash
pip install valgebra-vtjson
# optional network/format validators:
pip install "valgebra-vtjson[formats]"   # email, domain_name
pip install "valgebra-vtjson[magic]"     # magic (needs system libmagic)
```

## Use

```python
import vtjson_compat as vtjson

schema = {"name": str, "age?": int}
vtjson.validate(schema, {"name": "Ada", "age": 36})  # passes
```

The compatibility surface mirrors vtjson's names. See
[docs/migrating-from-vtjson.md](docs/migrating-from-vtjson.md) for the full
mapping and the ledger of intentional behavioral differences.

> The compatibility layer is a migration path, not a destination. New code
> should use valgebra's native API directly.

## Development

This repo resolves `valgebra` from a sibling checkout (`../valgebra`). With both
repos cloned side by side:

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
