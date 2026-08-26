# Translation

How a vtjson schema spec becomes a valgebra validator. `_translate` in
`vtjson_compat/_translate.py` owns this; everything here is a claim about that
function and the helpers it calls.

## Classification is a chain, and order is meaning

`_translate` asks a series of questions and the first "yes" wins. The order is
not arbitrary — it mirrors vtjson's own dispatch, and swapping two arms changes
what a schema means.

The arms, in order: an already-built validator returns itself; `None`; `Any`; a
class; the four builtin container literals (`dict`, `list`, `tuple`, set); a
container written in some other class; anything else, which is a leaf.

Two of those arms exist because of a question the chain must not ask twice:

- **A class arm that also excludes subscripted generics.** `isinstance(schema,
  type)` is not enough on its own — see
  [04-interpreters.md](04-interpreters.md). The arm asks
  `get_origin(schema) is None` beside it.
- **A "container in some other class" arm** after the builtins, because vtjson
  dispatches a container on its abstract kind and only then demands the value be
  the literal's own class. `_foreign_kind` answers which builtin it reads as.

## The leaf, and the forms that hide inside it

`_translate_leaf` handles what is not a container. Three things happen there, and
each is a rule vtjson applies that a naive reading misses:

**`Annotated[T, *rest]` is `T` and every one of `rest`, each a schema.** A
construct written in the metadata *constrains* the value. Handing the whole form
to valgebra instead reads the metadata by valgebra's own marker protocol, where a
vtjson construct is not a marker — so the constraint would be dropped rather than
applied.

**A subscripted generic is a schema, not a callable.** Several are callable, and
calling one builds a container from the value rather than judging it:
`list[int]("a")` is `["a"]`, which a predicate reads as a pass.

**A bare callable is a predicate over any value**, which is vtjson's convention.

## A generic is read by what its origin is

vtjson does not privilege the builtins. A `Mapping` subclass gives a mapping over
two arguments, any other `Container` subclass a collection over one, and the
value must be an instance of the origin as well. So `Sequence[int]`,
`Mapping[str, int]`, `deque[int]` and `OrderedDict[str, int]` are ordinary
schemas.

valgebra builds its container nodes from the builtins, so an origin outside them
gets the same treatment as a container literal written in a foreign class: the
shape is decided by the equivalent builtin over a converted value, and the origin
by an atom beside it. A value that will not convert is not one the origin admits.

An origin naming neither kind keeps vtjson's fallback — an instance check if the
form answers to `type`, a call otherwise. That is one question, not an
interpreter branch; the interpreter supplies the difference.

## Strictness travels with the translation

vtjson threads strictness as a call-time flag, so it reaches every record the
schema names wherever that record is written. This layer settles it while
building, which means `open_records` has to be carried through **every**
recursive call: container arms, alias arguments, `Annotated` metadata, and the
leaf.

The rule strictness expresses: laxness frees only what a schema does **not**
declare — a key no clause claims, a position after the declared ones. A typed
catch-all is a clause either way, so neither mode may discard it.

Nesting follows vtjson without a flag, and the mechanism is worth knowing: a
wrapper builds a validator, a validator carries the mode it was built with, and
translating a built validator yields it unchanged. So an enclosing wrapper cannot
reach inside one and the innermost mode stands — which is what vtjson's call-time
flag arrives at by another route.

## Both spellings of a union

`X | Y` and `Union[X, Y]` do not report the same origin on every supported
interpreter, and a union is built from the *translated* arguments rather than by
subscripting `Union`. Both facts are interpreter-shaped; see
[04-interpreters.md](04-interpreters.md).

## Arguments are checked when the schema is built

A bound that cannot be compared against, a pattern that will not compile, a
generic carrying the wrong number of arguments: each denotes no set of values and
raises `SchemaError`, as it does in vtjson.

The check is not cosmetic. A bound valgebra cannot read contributes no
constraint, so the refinement would widen to **every** value rather than
narrowing — a schema that silently stops enforcing is worse than one that
refuses to build.
