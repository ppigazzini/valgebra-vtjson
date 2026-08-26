# Architecture

What the layer is made of, and where valgebra enters.

## The shape

A vtjson schema is a Python object — a `dict`, a `list`, a type, a construct — and
vtjson decides membership by walking that object beside the value, every call,
in Python. This layer walks it **once**, into a valgebra validator, and then
valgebra decides.

```
vtjson schema spec  ──_translate──▶  valgebra validator  ──is_valid──▶  verdict
```

Everything downstream of the arrow is valgebra's. The layer's job is the arrow:
say which set of Python values a vtjson schema denotes, and build the valgebra
node that denotes the same set.

## Modules

| Module | Owns |
|---|---|
| `vtjson_compat/_valgebra_api.py` | every valgebra name the package uses |
| `vtjson_compat/_translate.py` | classification, containers, strictness |
| `vtjson_compat/_constructs.py` | the combinators, refinements, modifiers, wrappers |
| `vtjson_compat/_formats.py` | the string and network format validators |
| `vtjson_compat/__init__.py` | the public surface |

## The valgebra boundary is one file

`_valgebra_api.py` is the only module that imports valgebra, and it imports from
the `valgebra` package rather than the `valgebra._valgebra` extension underneath
it. What the extension exports is an implementation detail; `valgebra.__all__` is
the surface valgebra supports.

The invariant: **a valgebra rename is one file's worth of edit here.** A direct
import anywhere else spreads the coupling and the next valgebra release finds it.

The aliases also let the rest of the package read in vtjson's vocabulary while
the algebra keeps its own — `union` is valgebra's, `_union` is what the
translator calls it.

## Build it out of valgebra

The translation is the design. Where vtjson is lax, the lax meaning is expressed
**with the algebra** rather than by weakening a primitive: vtjson's `float`
admits ints, so it becomes `union(int, float)`, not a loosened float atom.

A Python predicate is valgebra's documented callback path and it is opaque to
the algebra — it cannot be simplified, intersected, or explained, and it costs a
call per value. So it is the last resort, and it is kept as small as the dynamic
part of the meaning:

- A container schema written in a class valgebra has no node for is an **atom
  for the class** intersected with a **narrow predicate** that decides the shape
  over a converted value. Not one predicate doing both.
- A refinement whose bound valgebra can read is a refinement, not a comparison
  in Python.

When the algebra genuinely cannot denote the set, that is a valgebra finding
with a set of values attached, not a predicate quietly written here.

## What this layer is for

It is a compatibility layer, and it is a harness. Driving a second
implementation over the same inputs as valgebra makes disagreements audible: a
defect in either library shows up as a divergence, and some of the divergences
found here have been valgebra's rather than this layer's.

That is why the parity contract is strict. A layer that quietly improves on its
oracle stops being able to tell you which of the two is wrong.
