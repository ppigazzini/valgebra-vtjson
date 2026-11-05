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
| `get_origin(X \| Y)` | `types.UnionType` | `typing.Union` in 3.14 |
| `isinstance(typing.Union, type)` | `False` | `True` in 3.14 |

## What each one does if it is missed

- **Two spellings of a union.** Recognising one origin and not the other leaves
  half the unions handed over whole, so laxness and translated arguments stop at
  them. Both spellings are listed.
- **The bare `typing.Union` becoming a class.** From 3.14 it is
  `types.UnionType`, so it reaches the class arm, which vtjson reads as an
  instance check. valgebra reads the same object as the typing form and builds
  nothing, so the class arm asks `isinstance` itself wherever valgebra builds no
  validator, rather than letting the refusal out on one interpreter.

## Why reading the code does not find these

None of them is a mistake in the rule the layer implements. Each is the *same*
rule asked of an interpreter that answers differently — correct on the version
in front of you, wrong one version down.

That is also why the local gate hides them: it runs one interpreter.

## The rule

**Run the parity suite on both ends of the supported range before committing a
change that classifies a schema.**

```bash
uv sync --locked --python 3.11 && uv run --no-sync pytest
uv sync --locked --python 3.15 && uv run --no-sync pytest
```

Check the two owners named at the top rather than trusting that pair to still be
the ends.

## The build is part of the interpreter

A version is not an interpreter. 3.13, 3.14 and 3.15 each ship a free-threaded
build as well as a standard one, and they are different runtimes: the translator
keeps per-thread state while it descends a schema, and under a GIL that state is
held still by the interpreter rather than by anything here.

`.github/workflows/ci.yml` runs a free-threaded lane for that reason. Locally,
`--python 3.15` resolves to whichever 3.15 is installed rather than to a build
you chose, so ask before assuming:

```bash
python -c "import sysconfig; print(sysconfig.get_config_var('Py_GIL_DISABLED'))"
```

`0` is a GIL build, `1` is free-threaded. It matters for measurement as well as
for correctness — see [06-performance.md](06-performance.md), whose figures are
a GIL build's.

## The limit

The ends are not a proof about the middle. They catch the common case, where a
behaviour changed once and stayed changed; they would miss a behaviour that
changed and changed back. CI runs every interpreter in the matrix, and that is
what actually covers the range — the local pair is for finding the break before
it gets there.
