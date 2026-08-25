# Changelog

All notable changes to valgebra-vtjson are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.1] - 2026-08-25

The first version carrying a number. Every entry below is a decision the
layer reaches the same way vtjson does, established by running both.

### Added

- `SchemaError`. A construct checks its own arguments when the schema is
  built and refuses one that cannot express a set of values, as vtjson does.
  Without the check a bound valgebra cannot read contributes no constraint, so
  `gt(None)` admitted every value; a pattern nothing can match rejected every
  value. Both looked like working validators.

### Fixed

- `interval` reads `...` on either end as unbounded, matching `size`.
- The dict-key modifiers constrain a `Mapping`. Counting with `in` admitted any
  container holding the candidate, and a non-mapping satisfied `at_most_one_of`
  and a zero-arity `keys`.
- A bare float constant is a tolerance rather than an identity, at every
  position a constant can appear. A float *key* stays exact, as in vtjson.
- `div` counts `(value - remainder) % divisor`, which is the class `remainder`
  represents. A third of its legal argument space decided differently.
- `float_` and `number` each carry both spellings vtjson accepts, bare and
  called.
- `ifthen` reads `else_schema=None` as no else-branch. Translating the `None`
  demanded the value *be* `None`, inverting the construct.
- A dict key claimed by more than one clause belongs when any of them admits
  the value, so a named field its own catch-all also claims has two ways to
  pass.
- A container schema carries the class it is written in: an `OrderedDict`
  schema admits no plain `dict`, and a named tuple schema no plain tuple.
- A value that raises while being inspected is reported as a failing value
  rather than as a broken predicate, and `unique` compares members it cannot
  hash instead of rejecting them.
- The construct signatures are vtjson's, argument names included, so a call
  written by keyword ports unchanged. `make_type` carries `subs` and
  `optional_key` carries `_optional`; `cond` carries no `default`, which vtjson
  has no equivalent for.
- The recursion an error points at is `recursive`, and each optional
  construct's `ImportError` names the extra that provides it.

[Unreleased]: https://github.com/ppigazzini/valgebra-vtjson/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/ppigazzini/valgebra-vtjson/releases/tag/v0.0.1
