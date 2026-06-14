# Migrating from vtjson

`vtjson_compat` is a compatibility layer that reads vtjson-style
schemas and reaches the same accept/reject decision as vtjson. Migration is
mostly an import change, plus the differences recorded in the ledger below.

> The compatibility layer is the migration path, not the destination. New code
> can use valgebra's native API (typing annotations, the `union`/`intersect`/
> `complement` algebra, and the `lazy` fixpoint) directly.

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
`number`.

## Optional extras

Some validators reuse the same third-party packages vtjson uses. They are not
valgebra runtime dependencies; install the extra that you need:

- `pip install "valgebra-vtjson[formats]"` — `email` and `domain_name`
  (`email-validator`, `idna`, `dnspython`).
- `pip install "valgebra-vtjson[magic]"` — `magic` (`python-magic`, which needs
  the system libmagic library).

Calling one of these validators without its extra installed raises a clear
`ImportError` that names the extra. vtjson installs these heavy dependencies
unconditionally; valgebra makes them opt-in.

## Differences ledger

Every intentional difference, with its migration note. Almost all concern types,
errors, dependencies, and a few unsupported forms and do **not** change the
accept/reject decision. The one exception, flagged **decision** below, is a place
where valgebra deliberately decides differently because vtjson is wrong.

| Area | vtjson | valgebra compat | Migration note |
| --- | --- | --- | --- |
| **Literal / constant equality (decision)** | a constant matches by Python `==`, so `1` also accepts `True` and `1.0` (and `0` accepts `False`) | a constant is a *typed singleton*: a value must have the same type and be equal, so `1` rejects `True`/`1.0` | This is a deliberate correctness fix — the typing spec treats `Literal[1]`, `Literal[True]`, `Literal[1.0]` as distinct. If you relied on the cross-type match, widen the schema explicitly (e.g. `union(1, True)`). |
| Error type | raises `vtjson.ValidationError` | raises `valgebra` `ValidationError` (a different class, with structured `code`/`path`/`expected`/`value`) | Catch `vtjson_compat.ValidationError`. `is_valid`-style checks never raise. |
| Error report | one first-failure string | one structured violation | Read `err.code`/`err.path` instead of parsing a message. |
| `float` | also admits `int` | mapped to `union(int, float)`, so the decision matches | None — parity holds. valgebra's own `float` is floats-only, equal to vtjson's `float_`. |
| Recursion | `set_label` + validate-time `subs` | not supported; `set_name`/`set_label` are accepted but their labels are ignored | Express recursion with valgebra's `lazy` fixpoint. |
| `magic` | always available (libmagic installed) | needs the `vtjson-magic` extra | Install the extra, or replace with a predicate. |
| `email`, `domain_name` | always available | need the `vtjson-formats` extra | Install the extra. |
| Raising predicate | swallowed into a generic failure | surfaced as a distinct `predicate_error` | A crashing predicate is now visible; fix the predicate. |
| `Apply` / `skip_first` | reorder how `Annotated` arguments apply | not supported (the layer applies `Annotated` metadata in declaration order) | Reorder the `Annotated` arguments instead; valgebra has no apply-order modifier. |

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
`isinstance` check, and `lazy` respectively. **Every fishtest schema conforms;
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
