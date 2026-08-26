# Interpreters

The layer classifies a schema by asking the typing runtime what it is. Those
answers change between CPython releases, so the interpreter is a dimension the
layer varies over whether or not anyone tests it.

**Read this page before changing anything in
[01-translation.md](01-translation.md)'s classification chain.**

`requires-python` in `pyproject.toml` owns the floor;
`.github/workflows/ci.yml` owns the interpreters CI runs.

## What changes underneath

Each row is a CPython behaviour, not a configuration choice — it does not expire
and it cannot be fixed here.

| Question the layer asks | Answer before | Answer from |
|---|---|---|
| `isinstance(dict[str, int], type)` | `True` | `False` in 3.11 |
| `Union[x]` where `x` is not a type | `TypeError` | accepted in 3.11 |
| `isinstance(Any, type)` | `False` | `True` in 3.11 |
| `get_origin(X \| Y)` | `types.UnionType` | `typing.Union` in 3.14 |

## What each one does if it is missed

- **A subscripted generic answering to `type`.** The class arm swallows every
  `list[int]` and `dict[str, int]` before the alias arm can take it apart, so a
  construct written inside one is silently dropped. The guard is asking
  `get_origin(schema) is None` beside `isinstance(schema, type)`.
- **`Union` refusing a non-type argument.** A union rebuilt from *translated*
  arguments carries validators, not types. Build it with valgebra's `union`
  rather than by subscripting `Union`, and the question never arises.
- **`Any` not being a class.** It falls past the class arm to the constant arm
  and admits only itself, where vtjson admits everything. `Any` gets its own arm.
- **Two spellings of a union.** Recognising one origin and not the other leaves
  half the unions handed over whole, so laxness and translated arguments stop at
  them. Both spellings are listed.

## Why reading the code does not find these

None of them is a mistake in the rule the layer implements. Each is the *same*
rule asked of an interpreter that answers differently — correct on the version
in front of you, wrong one version down.

That is also why the local gate hides them: it runs one interpreter. Three of
these were introduced and caught inside a single commit; one had been shipping
since the layer existed, because `Any` is not a container, not a construct and
not a callable, so it belonged to no surface any sweep had enumerated.

## The rule

**Run the parity suite on both ends of the supported range before committing a
change that classifies a schema.**

```bash
uv sync --locked --python 3.10 && uv run --no-sync pytest
uv sync --locked --python 3.14 && uv run --no-sync pytest
```

Check the two owners named at the top rather than trusting that pair to still be
the ends.

## The limit

The ends are not a proof about the middle. They catch the common case, where a
behaviour changed once and stayed changed; they would miss a behaviour that
changed and changed back. CI runs every interpreter in the matrix, and that is
what actually covers the range — the local pair is for finding the break before
it gets there.
