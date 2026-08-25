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

The compatibility surface mirrors vtjson's names: `validate`, the combinators
(`union`, `intersect`, `complement`, `ifthen`, `cond`), the dict-key modifiers
(`keys`, `one_of`, `at_least_one_of`, `at_most_one_of`), the structural checks
(`fields`, `protocol`), the comparison and size refinements (`gt`, `ge`, `lt`,
`le`, `interval`, `size`), the predicates (`unique`, `div`, `close_to`,
`filter`), the string formats (`regex`, `regex_pattern`, `glob`, `url`,
`ip_address`, `date_time`, `date`, `time`), the network formats (`email`,
`domain_name`), the wrappers (`lax`, `strict`, `quote`, `set_name`, `set_label`,
`make_type`, `safe_cast`), and `anything`/`nothing`/`optional_key`/`float_`/
`number`, plus the two error types `ValidationError` and `SchemaError`.

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
| `lax`/`strict` nesting | the innermost wrapper wins: a `lax` inside a `strict` stays open, because each wrapper imposes its mode on everything below it | the outermost wins: `lax` and `strict` set a flag on the compiled record, so the last one applied decides. `validate(..., strict=False)` likewise opens a record an inner `strict()` closed | Apply the wrapper you mean at the outermost point, and do not rely on an inner wrapper overriding an outer one. |
| `lax` over a catch-all | a key the catch-all claims must still satisfy it; laxness excuses only a key no clause claims | opening a record drops its catch-all clause, so a claimed key with a failing value is admitted | Validate the mixed dict without `lax`, or state the permitted extra keys as another clause. |
| Fixed-length sequences | `len(obj)` is called, so a `list` subclass with a raising `__len__` crashes the call | the real sequence is read without invoking a Python-level `__len__` override, so such a value is judged on its actual contents | None for ordinary values. A `list` subclass that lies about its length is validated on what it holds. |
| `make_type`'s `subs` | performs the substitution | accepts the argument and raises `NotImplementedError` when it is non-empty | Express recursion with valgebra's `recursive` fixpoint. Ignoring the argument would build a type over a schema the caller did not ask for. |
| `Apply` / `skip_first` | reorder how `Annotated` arguments apply | not supported (the layer applies `Annotated` metadata in declaration order) | Reorder the `Annotated` arguments instead; valgebra has no apply-order modifier. |

A dict key that more than one clause claims — a named field whose own
catch-all also matches its name — belongs when **any** of those clauses admits
the value, as in vtjson. Which catch-alls claim a literal key is settled when
the schema is built, so the check costs nothing per value.

The prefix-plus-repeated-tail list `[A, B, ...]`, the matching tuple shapes
(`(T, ...)` and `(A, B, ...)`), multi-element sets (`{A, B}`, where every member
matches `A` or `B`), and heterogeneous mappings (several key-schema →
value-schema clauses, or a named key mixed with a key-schema catch-all, e.g.
`{str: int, int: str}` or `{"name": str, str: int}`) were once recorded here as
unsupported. valgebra has since grown a sequence-regex node (now wired through
the tuple frontend as well) and a keyed-default mapping node, so all of them
translate with exact parity and are no longer divergences.

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
run_id}`) that valgebra's keyed-default mapping now expresses. fishtest's own
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
