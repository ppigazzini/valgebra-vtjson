# vtjson conformance

`vtjson_compat` reads vtjson-style schemas and validates them through valgebra,
reaching the same accept/reject decision as vtjson. This document is the record
of that conformance: the construct-by-construct mapping, and a ledger of the few
places where valgebra intentionally decides differently. Pointing an existing
vtjson schema at valgebra is mostly an import change, plus the differences below.

> This layer is a supported, tested way to run vtjson schemas on valgebra, for as
> long as you need it. For *new* schemas, valgebra's native API — typing
> annotations, the `union`/`intersect`/`complement` algebra, and the `recursive`
> fixpoint — is usually the more direct expression.

## The import change

Replace the vtjson import with the compatibility layer:

```python
import vtjson_compat as vtjson

schema = {"name": str, "age?": int}
vtjson.validate(schema, {"name": "Ada", "age": 36})  # passes
```

The compatibility surface mirrors vtjson's names. Every name on vtjson's
public surface is classified in `tests/test_parity_inventory.py` as supported,
ledgered here as an intentional difference, or not a schema construct at all —
and the three sets must cover that surface exactly, so a vtjson release adding
a construct fails the suite until someone classifies it. Read that file for the
roll-call; a second copy in this page could only drift away from it.

A container class that is not a builtin — a `UserDict`, a `Counter`, a
`UserList`, a `deque` — is still a container schema: it is read for its shape
and admits only its own class, as in vtjson. Text is excluded, because a string
is a sequence of strings and reading one that way descends forever.

A container schema carries the class it is written in: an `OrderedDict` schema
admits no plain `dict`, and a named tuple schema admits no plain tuple, as in
vtjson. A `frozenset` schema is uninhabited for the same reason it is in vtjson
— the set shape wants a `set` and the class wants a `frozenset`.

The construct signatures are vtjson's, argument names included, so a call
written by keyword ports unchanged. `cond` takes cases and nothing else: a
default clause is a trailing `(anything, then)` case, as in vtjson.

## Optional extras

Some validators reuse the same third-party packages vtjson uses. They are not
valgebra runtime dependencies; select the extra that you need when installing
from the Git repository:

- `[formats]` — `email` and `domain_name` (`email-validator`, `idna`,
  `dnspython`).
- `[magic]` — `magic` (`python-magic`, which needs the system libmagic
  library).

Calling one of these validators without its extra installed raises a clear
`ImportError` that names the extra. vtjson installs these heavy dependencies
unconditionally; valgebra makes them opt-in.

## Differences ledger

Every intentional difference, with its note. Almost all concern types, errors,
dependencies, and a few unsupported forms and do **not** change the accept/reject
decision. The one exception, flagged **decision** below, is a place where
valgebra follows the typing spec's model of literals and so decides differently.

| Area | vtjson | valgebra compat | Migration note |
| --- | --- | --- | --- |
| **Literal / constant equality (decision)** | a constant matches by Python `==`, so `1` also accepts `True` and `1.0` (and `0` accepts `False`) | a constant is a *typed singleton*: a value must have the same type and be equal, so `1` rejects `True`/`1.0`. A **float** constant carries vtjson's tolerance within that type, so `1.5` admits any float `math.isclose` calls close to it and no `int` at all | valgebra follows the typing spec, which treats `Literal[1]`, `Literal[True]`, and `Literal[1.0]` as distinct singletons. If you relied on the cross-type match, widen the schema explicitly (e.g. `union(1, True)`). |
| Malformed schema | raises `vtjson.SchemaError` when a construct's arguments cannot express a set of values | raises `vtjson_compat.SchemaError`, a different class with the same role | Catch `vtjson_compat.SchemaError`. Both refuse the schema at construction, so a bound nothing can be ordered against, or a pattern nothing can match, never becomes a validator with a constant verdict. |
| Error type | raises `vtjson.ValidationError` | raises `valgebra` `ValidationError` (a different class, with structured `code`/`path`/`expected`/`value`) | Catch `vtjson_compat.ValidationError`. `is_valid`-style checks never raise. |
| Error report | one first-failure string | one structured violation | Read `err.code`/`err.path` instead of parsing a message. |
| `float` | also admits `int` | mapped to `union(int, float)`, so the decision matches | None — parity holds. valgebra's own `float` is floats-only, equal to vtjson's `float_`. |
| Recursion | `set_label` + validate-time `subs` | not supported; `set_name`/`set_label` are accepted but their labels are ignored | Express recursion with valgebra's `recursive` fixpoint. |
| `magic` | always available (libmagic installed) | needs the `valgebra-vtjson[magic]` extra | Install the extra, or replace with a predicate. |
| `email`, `domain_name` | always available | need the `valgebra-vtjson[formats]` extra | Install the extra. |
| A value that raises under inspection | most constructs let the exception out of `validate`, so a value with a raising `__len__`, `__contains__`, `__eq__` or property crashes the call | the value is rejected, and the violation names the value rather than the predicate that inspected it | Catch `ValidationError`, not the value's own exception. A rejection where vtjson crashes is the one direction this layer does not follow it. |
| Your own raising predicate | swallowed into a generic failure | surfaced as a distinct `predicate_error` | Read `err.code`: `predicate_error` means the callable you supplied raised, which is a bug in the predicate rather than a property of the value. |
| Fixed-length sequences | `len(obj)` is called, so a `list` subclass with a raising `__len__` crashes the call | the real sequence is read without invoking a Python-level `__len__` override, so such a value is judged on its actual contents | None for ordinary values. A `list` subclass that lies about its length is validated on what it holds. |
| `make_type`'s `subs` | performs the substitution | accepts the argument and raises `NotImplementedError` when it is non-empty | Express recursion with valgebra's `recursive` fixpoint. Ignoring the argument would build a type over a schema the caller did not ask for. |
| Schema nesting depth | unbounded short of Python's own recursion | a schema reaching 128 levels of valgebra nesting is refused when it is built; a one-element list costs about three levels per source level, so `[[[…]]]` reaches its limit at 43 | Flatten the schema, or express the repetition with a homogeneous `[T, ...]`, which costs one level. |
| `Apply` / `skip_first` | reorder how `Annotated` arguments apply | not supported (the layer applies `Annotated` metadata in declaration order) | Reorder the `Annotated` arguments instead; valgebra has no apply-order modifier. |

Strictness settles only what happens to a key or a position the schema does
**not** declare: `strict` rejects it, `lax` admits it. A fixed-length sequence
declares positions the way a record declares keys, so a lax `[int, str]` checks
those two and admits whatever follows them, and a `TypedDict` declares keys the
same way. A class that declares nothing — an instance check, an enum — has no
undeclared member for laxness to free. A record's named fields and its typed catch-all are
clauses either way, so neither mode discards them. Nesting follows vtjson too —
each wrapper builds a validator, and an enclosing wrapper cannot reach inside
one, so the innermost mode stands.

Strictness reaches the record a combinator carries: `lax(union({"a": int},
str))` frees the record's undeclared keys, as it does in vtjson, and so do
`intersect`, `ifthen`, `cond`, `complement`, `filter`, `set_name` and `protocol`.
`set_label` is the exception, and it is vtjson's: a labelled schema is validated
strictly whatever the ambient flag says, so neither an enclosing `lax` nor
`validate(strict=False)` reaches inside it.

`Annotated[T, *rest]` is `T` and every one of `rest`, each read as a schema in
its own right, as vtjson reads it — so a construct written in the metadata
constrains the value rather than decorating it, including inside a subscripted
generic such as `dict[str, Annotated[int, ge(0)]]`.

A subscripted generic is read by what its origin is, not by whether that origin
is a builtin. A `Mapping` subclass gives a mapping over the two arguments and a
`Container` subclass a collection over the one, and the value must be an
instance of the origin as well — so `Sequence[int]`, `Mapping[str, int]`,
`deque[int]` and `OrderedDict[str, int]` all decide as they do in vtjson, and
the wrong number of arguments is a `SchemaError` rather than a verdict. An
origin that names neither kind falls back on vtjson's own rule for a schema it
cannot place, which reads the form as an instance check if it answers to `type`
and calls it otherwise. `type[int]` is the form where that distinction is
visible: before 3.11 a subscripted generic answers `isinstance(..., type)`, so
it admits nothing, and from 3.11 it is called instead and admits everything.
Both libraries flip together.

A class written as a schema is read by what kind of class it is. A `TypedDict`,
a `Protocol` and a `NamedTuple` are **structural**: the type hints the class
declares are checked against the value's items or attributes, and the value's
own class is never consulted. So two `NamedTuple`s declaring the same field are
the same schema, a wider value satisfies a narrower schema, and a `NamedTuple`
schema additionally demands a tuple. `runtime_checkable` does not enter into it
— it governs `isinstance`, which asks only whether an attribute is present,
where the schema also enforces its declared type. Every other class — a
dataclass, an enum, a plain class — is an instance check.

A class that declares no hints constrains nothing, so it admits every value.
That holds for a bare `collections.namedtuple` used as a schema, which therefore
admits every tuple, and for `protocol` applied to such a class. Only a class
carrying no annotations at all is refused, with a `SchemaError`.

A dict key that is not a string is a **clause** when it is a schema and a
**declared key** when it is a constant: `{int: str}` says nothing about a
mapping with no int key, and `{1: str}` says the mapping carries a `1`.

A dict key that more than one clause claims — a named field whose own
catch-all also matches its name — belongs when **any** of those clauses admits
the value, as in vtjson. Which catch-alls claim a literal key is settled when
the schema is built, so the check costs nothing per value.

The prefix-plus-repeated-tail list `[A, B, ...]`, the matching tuple shapes
(`(T, ...)` and `(A, B, ...)`), multi-element sets (`{A, B}`, where every member
matches `A` or `B`), and heterogeneous mappings (several key-schema →
value-schema clauses, or a named key mixed with a key-schema catch-all, e.g.
`{str: int, int: str}` or `{"name": str, str: int}`) all translate with exact
parity: valgebra's sequence-regex node carries the list and tuple shapes, and
its keyed-default mapping node carries the rest.

## Conformance against fishtest

The compatibility layer is checked against the real
[fishtest](https://github.com/official-stockfish/fishtest) schemas, which are
fetched at a pinned commit and run through both vtjson and the compatibility
layer. Every string-keyed schema — including the full run document
(`runs_schema`), `api_schema`, `action_schema`, and `results_schema` — reaches
the same accept/reject decision. All six schema-keyed tables reach identical
decisions too: `cache_schema`, `wtt_map_schema`, `connections_counter_schema`,
`books_schema`, the `unfinished_runs_schema` set, and `worker_runs_schema` —
whose value is a *mixed* record-plus-catch-all (`{run_id: True, "last_run":
run_id}`) that valgebra's keyed-default mapping expresses. fishtest's own
`magic`, `ObjectId`, and `set_label`/`subs` usages map to the optional extras, an
`isinstance` check, and `recursive` respectively. **Every fishtest schema conforms;
no schema is unsupported.**

## A worked example

```python
import vtjson_compat as vtjson


def is_valid(schema: object, obj: object) -> bool:
    try:
        vtjson.validate(schema, obj)
    except vtjson.ValidationError:
        return False
    return True


run = {
    "id": vtjson.regex(r"[0-9a-f]{24}"),
    "games": vtjson.intersect(int, vtjson.ge(0)),
    "state": vtjson.union("pending", "active", "finished"),
    "config": vtjson.lax({"priority?": int}),  # extra keys allowed
}

ok = {
    "id": "0123456789abcdef01234567",
    "games": 10,
    "state": "active",
    "config": {"priority": 1, "note": "extra ok"},
}
assert is_valid(run, ok)

bad = {"id": "nope", "games": -1, "state": "paused", "config": {}}
assert not is_valid(run, bad)
```
