"""A differential sweep of the oracle's whole public API, by call.

This suite belongs to valgebra-vtjson. It is written from the signatures vtjson
publishes and shares nothing with `test_vtjson.py`, vtjson's own suite in its
repository: that file checks vtjson against answers its author expects, and this
one holds the layer to whatever the pinned vtjson answers, so it states no
expected verdict at all.

The axis is the call: every public name, at every parameter it declares, crossed
with where the schema sits and how it is asked. `test_every_parameter_is_swept`
fails on a name or a parameter no row reaches, so a vtjson release that grows one
cannot go unswept.

An outcome is what a caller can tell apart: admitted, refused, a schema refused,
or some other exception, whichever stage raised it. A message is not compared,
as `docs/03-conformance.md` records.
"""

from __future__ import annotations

import datetime as dt
import decimal
import enum
import fractions
import inspect
import math
import pathlib
import re
import typing
from collections import OrderedDict, UserDict, UserList, defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NamedTuple, Protocol, TypedDict

import pytest
import vtjson as vt

import vtjson_compat as vg

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

# Two rows ask for what is deprecated: `number`, and the truth of `NotImplemented`,
# which a constant of it reaches before 3.14 raises for it.
pytestmark = [
    pytest.mark.filterwarnings("ignore:The schema 'number' is deprecated"),
    pytest.mark.filterwarnings("ignore:NotImplemented should not be used"),
]

_LEDGER = (
    pathlib.Path(__file__).resolve().parent.parent / "docs" / "03-conformance.md"
).read_text(encoding="utf-8")


class _Plain:
    pass


@dataclass
class _Data:
    x: int = 1
    y: str = "a"


class _Pair(NamedTuple):
    x: int
    y: str


class _Color(enum.Enum):
    RED = 1


class _Attributes:
    """An object answering the attributes the `fields` and `protocol` rows ask."""

    def __init__(self, x: object = 1, y: object = "a") -> None:
        self.x = x
        self.y = y


class _Hinted(Protocol):
    x: int
    y: str


class _HintedDict(TypedDict):
    x: int
    y: str


class _Unhinted:
    pass


_Named = typing.NewType("_Named", int)
# A `NamedTuple` holding schemas where its fields declare values.
_PAIR_OF_TYPES: Any = _Pair(*typing.cast("tuple[Any, Any]", (int, str)))


class _Reversed(int):
    """An integer ordered the other way round, by comparisons of its own."""

    def __ge__(self, other: Any) -> bool:
        return int(self) <= other

    def __le__(self, other: Any) -> bool:
        return int(self) >= other

    def __gt__(self, other: Any) -> bool:
        return int(self) < other

    def __lt__(self, other: Any) -> bool:
        return int(self) > other


# Ordinary values of every kind a construct distinguishes. A value that raises
# when it is inspected is `test_hostile_values.py`'s surface.
VALUES: list[object] = [
    None,
    True,
    False,
    0,
    1,
    -1,
    2,
    3,
    10,
    2**70,
    0.0,
    1.0,
    1.5,
    -0.5,
    1e300,
    math.inf,
    -math.inf,
    math.nan,
    1j,
    decimal.Decimal("1.5"),
    fractions.Fraction(1, 2),
    "",
    "a",
    "A",
    "abc",
    "1",
    "1.5",
    "2024-01-31",
    "2024-01-31T10:20:30",
    "10:20:30",
    "not a date",
    "user@example.com",
    "user@",
    "example.com",
    "münchen.de",
    "http://example.com/a?b=1",
    "not a url",
    "1.2.3.4",
    "::1",
    "256.0.0.1",
    "a.py",
    "dir/a.py",
    "[",
    b"",
    b"a",
    b"%PDF-1.4",
    bytearray(b"a"),
    [],
    [1],
    [1, 2],
    [1, 1],
    ["a"],
    [1, "a"],
    [[1]],
    [None],
    (),
    (1,),
    (1, 2),
    (1, "a"),
    (1, "a", 2),
    (1, 2, 3),
    [1, 2, 3],
    [1, "a", 2],
    set(),
    {1},
    {"a"},
    frozenset({1}),
    {},
    {"a": 1},
    {"a": "x"},
    {"b": 1},
    {"a": 1, "b": 2},
    {"a": 1, "b": "x"},
    {"x": 1, "y": "a"},
    {"x": 1, "y": "a", "z": 2},
    {1: "a"},
    {None: 1},
    {b"a": 1},
    {(1,): 1},
    {1.5: 1},
    OrderedDict(a=1),
    defaultdict(int, {"a": 1}),
    UserDict(a=1),
    UserList([1]),
    deque([1]),
    range(2),
    int,
    str,
    len,
    _Plain(),
    _Data(),
    _Pair(1, "a"),
    _Color.RED,
    _Attributes(),
    _Attributes("a", 1),
    dt.date(2024, 1, 31),
    dt.datetime(2024, 1, 31, 10, 20, 30, tzinfo=dt.UTC),
    dt.time(10, 20, 30),
    re.compile("a"),
    pathlib.PurePosixPath("a.py"),
    object(),
]


def _identity(obj: object) -> object:
    return obj


def _length(obj: Any) -> int:
    return len(obj)


def _upper(obj: Any) -> str:
    return obj.upper()


def _is_truthy(obj: object) -> bool:
    return bool(obj)


class _Nested:
    """An argument spelled once and built per library, such as `m.ge(0)`."""

    def __init__(self, label: str, build: Callable[[Any], object]) -> None:
        self.label = label
        self.build = build

    def __repr__(self) -> str:
        return self.label


def _spelled(value: object) -> str:
    """Return a stable label for an argument, free of any memory address."""
    if isinstance(value, type) or inspect.isroutine(value):
        return value.__name__
    if value is Ellipsis:
        return "..."
    return repr(value)


def _resolved(value: object, module: Any) -> object:
    """Return ``value`` with each nested argument built for ``module``."""
    if isinstance(value, _Nested):
        return value.build(module)
    if type(value) is tuple:
        return tuple(_resolved(item, module) for item in value)
    return value


@dataclass(frozen=True)
class _Call:
    """One call of a public name, built once per library from one spelling."""

    name: str
    args: tuple[object, ...] = ()
    kwargs: Mapping[str, object] = field(default_factory=dict)

    @property
    def label(self) -> str:
        parts = [_spelled(a) for a in self.args]
        parts += [f"{k}={_spelled(v)}" for k, v in self.kwargs.items()]
        return f"{self.name}({', '.join(parts)})"

    def build(self, module: Any) -> object:
        return getattr(module, self.name)(
            *(_resolved(a, module) for a in self.args),
            **{k: _resolved(v, module) for k, v in self.kwargs.items()},
        )


def _call(name: str, /, *args: object, **kwargs: object) -> _Call:
    return _Call(name, args, kwargs)


_GE0 = _Nested("ge(0)", lambda m: m.ge(0))
_SIZE1 = _Nested("size(1)", lambda m: m.size(1))
_RECORD = {"a": int}

# Every construct at every parameter it declares, at the arguments that select a
# different reading and at those that denote no set of values.
CALLS: list[_Call] = [
    # The constructs taking nothing.
    *(
        _call(name)
        for name in (
            "number",
            "float_",
            "date",
            "time",
            "url",
            "unique",
            "regex_pattern",
        )
    ),
    # Text formats.
    _call("date_time"),
    _call("date_time", "%Y-%m-%d"),
    _call("date_time", format="%H:%M:%S"),
    _call("date_time", "%Y-%m-%dT%H:%M:%S"),
    _call("date_time", "literal"),
    _call("date_time", 1),
    _call("email"),
    _call("email", check_deliverability=False),
    _call("email", check_deliverability=True),
    _call("email", allow_smtputf8=False),
    _call("email", allow_quoted_local=True),
    _call("email", no_such_option=1),
    _call("domain_name"),
    _call("domain_name", True),
    _call("domain_name", ascii_only=False),
    _call("domain_name", resolve=False),
    _call("domain_name", resolve=True),
    _call("domain_name", ascii_only=False, resolve=True),
    _call("ip_address"),
    _call("ip_address", None),
    _call("ip_address", 4),
    _call("ip_address", version=6),
    _call("ip_address", 5),
    _call("ip_address", "4"),
    _call("regex", "a+"),
    _call("regex", "a"),
    _call("regex", "a", "named"),
    _call("regex", "a", name="named"),
    _call("regex", "a", 1),
    _call("regex", "a", fullmatch=False),
    _call("regex", "a", flags=re.IGNORECASE),
    _call("regex", "a", None, False, re.IGNORECASE),
    _call("regex", "["),
    _call("regex", 1),
    _call("regex", b"a"),
    _call("regex", "a", flags=re.ASCII | re.LOCALE),
    _call("regex", "a", flags="i"),
    _call("regex", r"\w{1,1000}"),
    _call("regex", "a{2}{3}"),
    _call("glob", "*.py"),
    _call("glob", "*.py", "named"),
    _call("glob", "*.py", name="named"),
    _call("glob", "**/*.py"),
    _call("glob", "a.py"),
    _call("glob", ""),
    _call("glob", 1),
    _call("glob", "*.py", 1),
    _call("magic", "text/plain"),
    _call("magic", "application/pdf"),
    _call("magic", "text/plain", "named"),
    _call("magic", "text/plain", name="named"),
    _call("magic", 1),
    _call("magic", "text/plain", 1),
    # Numbers.
    _call("div", 2),
    _call("div", 2, 1),
    _call("div", 3, remainder=1),
    _call("div", 2, name="named"),
    _call("div", 2, 1, "named"),
    _call("div", 0),
    _call("div", -2),
    _call("div", 1.5),
    _call("div", "a"),
    _call("div", 2, 1.5),
    _call("div", 2, "a"),
    _call("div", 2, name=1),
    _call("close_to", 1.5),
    _call("close_to", 1),
    _call("close_to", 0),
    _call("close_to", 1.5, 0.1),
    _call("close_to", 1.5, rel_tol=0.5),
    _call("close_to", 1.5, abs_tol=0.5),
    _call("close_to", 1.5, 0.1, 0.1),
    _call("close_to", 0, abs_tol=1),
    _call("close_to", "a"),
    _call("close_to", None),
    _call("close_to", 1.5, "a"),
    _call("close_to", 1.5, abs_tol="a"),
    _call("close_to", 1.5, rel_tol=-1),
    # Bounds, at each kind an order is defined on and some it is not.
    *(
        _call(name, bound)
        for name in ("gt", "ge", "lt", "le")
        for bound in (
            0,
            1,
            1.5,
            "a",
            b"a",
            decimal.Decimal("1.5"),
            fractions.Fraction(1, 2),
            math.inf,
            (1,),
            [1],
            {1},
            True,
            dt.date(2024, 1, 31),
            None,
            1j,
            _Plain,
            _Reversed(1),
            math.nan,
            decimal.Decimal("NaN"),
            decimal.Decimal("sNaN"),
        )
    ),
    _call("gt", lb=0),
    _call("ge", lb=0),
    _call("lt", ub=0),
    _call("le", ub=0),
    _call("interval", 0, 1),
    _call("interval", 0, ...),
    _call("interval", ..., 1),
    _call("interval", ..., ...),
    _call("interval", 0, 1, True),
    _call("interval", 0, 1, False, True),
    _call("interval", 0, 1, strict_lb=True),
    _call("interval", 0, 1, strict_ub=True),
    _call("interval", 0, 1, strict_lb=True, strict_ub=True),
    _call("interval", 1, 1),
    _call("interval", 1, 0),
    _call("interval", "a", "z"),
    _call("interval", 0, "z"),
    _call("interval", None, 1),
    _call("interval", 0, None),
    _call("interval", 0.5, 1.5),
    _call("interval", lb=0, ub=1),
    _call("interval", _Reversed(2), ...),
    _call("interval", ..., _Reversed(2)),
    _call("interval", _Reversed(2), _Reversed(1)),
    _call("interval", math.nan, 1),
    _call("interval", 0, math.nan),
    _call("interval", decimal.Decimal("NaN"), ...),
    _call("interval", decimal.Decimal("sNaN"), ...),
    _call("size", 0),
    _call("size", 1),
    _call("size", 1, 2),
    _call("size", 0, ...),
    _call("size", 1, ...),
    _call("size", lb=1, ub=2),
    _call("size", 2, 1),
    _call("size", -1),
    _call("size", 1.5),
    _call("size", "a"),
    _call("size", 0, "a"),
    _call("size", True),
    _call("size", 0, True),
    _call("size", _Reversed(2)),
    _call("size", 0, _Reversed(2)),
    _call("size", _Reversed(2), ...),
    # Mappings and objects.
    _call("fields", {"x": int}),
    _call("fields", d={"x": int}),
    _call("fields", {"x": int, "y": str}),
    _call("fields", {"x?": int}),
    _call("fields", {"z?": int}),
    _call("fields", {"x": str}),
    _call("fields", {}),
    _call("fields", {1: int}),
    _call("fields", 1),
    _call("fields", [("x", int)]),
    _call("keys", "a"),
    _call("keys", "a", "b"),
    _call("keys"),
    _call("keys", 1),
    _call("at_least_one_of", "a"),
    _call("at_least_one_of", "a", "b"),
    _call("at_least_one_of"),
    _call("at_most_one_of", "a"),
    _call("at_most_one_of", "a", "b"),
    _call("at_most_one_of"),
    _call("one_of", "a"),
    _call("one_of", "a", "b"),
    _call("one_of"),
    _call("protocol", _Hinted),
    _call("protocol", _HintedDict),
    _call("protocol", _HintedDict, dict=True),
    _call("protocol", _Hinted, True),
    _call("protocol", _Data),
    _call("protocol", _Pair),
    _call("protocol", _Unhinted),
    _call("protocol", 1),
    _call("protocol", _Hinted, dict=1),
    # A key is the one position `optional_key` means anything in, so that is
    # where its rows sit.
    # Combinators.
    _call("union"),
    _call("union", int),
    _call("union", int, str),
    _call("union", int, None),
    _call("union", _GE0, _SIZE1),
    _call("union", _RECORD, str),
    _call("intersect"),
    _call("intersect", int),
    _call("intersect", int, _GE0),
    _call("intersect", int, str),
    _call("intersect", _SIZE1, str),
    _call("complement", int),
    _call("complement", _GE0),
    _call("complement", None),
    _call("complement", _RECORD),
    _call("complement", object),
    _call("ifthen", int, _GE0),
    _call("ifthen", int, _GE0, str),
    _call("ifthen", if_schema=str, then_schema=_SIZE1, else_schema=int),
    _call("ifthen", int, _GE0, None),
    _call("cond"),
    _call("cond", (int, _GE0)),
    _call("cond", (int, str)),
    _call("cond", (bool, bool), (int, _GE0), (object, str)),
    _call("cond", (int,)),
    _call("cond", (int, str, bytes)),
    _call("cond", 1),
    _call("cond", [int, str]),
    _call("lax", _RECORD),
    _call("lax", [int]),
    _call("lax", (int,)),
    _call("lax", {int}),
    _call("lax", int),
    _call("strict", _RECORD),
    _call("strict", [int]),
    _call("strict", (int,)),
    _call("strict", int),
    _call("quote", 1),
    _call("quote", "a"),
    _call("quote", 1.5),
    _call("quote", None),
    _call("quote", [1]),
    _call("quote", (1,)),
    _call("quote", {"a": 1}),
    _call("quote", int),
    _call("set_name", _RECORD, "named"),
    _call("set_name", int, "named", True),
    _call("set_name", int, "named", reason=True),
    _call("set_name", schema=int, name="named"),
    _call("set_name", int, 1),
    _call("set_label", _RECORD, "label"),
    _call("set_label", int, "label", "other"),
    _call("set_label", int, "label", debug=True),
    _call("set_label", int),
    _call("set_label", int, 1),
    _call("filter", _length, _GE0),
    _call("filter", _length, 1),
    _call("filter", _upper, "A"),
    _call("filter", _identity, int),
    _call("filter", _length, _GE0, "named"),
    _call("filter", _length, _GE0, filter_name="named"),
    _call("filter", filter=_length, schema=_GE0),
    _call("filter", 1, int),
    _call("filter", _length, _GE0, 1),
]

# The names vtjson reads bare as well as called, since a bare construct class is
# instantiated when it is compiled.
NULLARY = (
    "anything",
    "nothing",
    "number",
    "float_",
    "date",
    "time",
    "url",
    "unique",
    "regex_pattern",
    "date_time",
    "email",
    "domain_name",
    "ip_address",
)

# `optional_key` means something only as a key, so its rows are whole schemas.
KEYED: list[tuple[_Call, Callable[[Any], object]]] = [
    (_call("optional_key", "a"), lambda m: {m.optional_key("a"): int}),
    (_call("optional_key", key="a"), lambda m: {m.optional_key(key="a"): int}),
    (_call("optional_key", "a", False), lambda m: {m.optional_key("a", False): int}),
    (
        _call("optional_key", "a", _optional=True),
        lambda m: {m.optional_key("a", _optional=True): str},
    ),
    (_call("optional_key", 1), lambda m: {m.optional_key(1): str}),
    (_call("optional_key", "a?"), lambda m: {m.optional_key("a?"): int}),
    (_call("optional_key", int), lambda m: {m.optional_key(int): str}),
    (_call("optional_key", "a"), lambda m: {m.optional_key("a"): int, "b": int}),
    (_call("optional_key", "a"), lambda m: {m.optional_key("a"): int, str: int}),
]

# Keys that may build one validator, whose clauses vtjson holds apart.
KEYS_ALIKE: list[tuple[str, Callable[[Any], object]]] = [
    ("int, union(int)", lambda m: {int: str, m.union(int): bytes}),
    ("int, intersect(int)", lambda m: {int: str, m.intersect(int): bytes}),
    ("int, Annotated[int]", lambda m: {int: str, typing.Annotated[int, object]: bytes}),  # noqa: ARG005
    (
        "union, union reversed",
        lambda m: {m.union(int, str): int, m.union(str, int): str},
    ),
    ("int | str, str | int", lambda m: {int | str: int, str | int: str}),  # noqa: ARG005
    ("Any, object", lambda m: {typing.Any: int, object: str}),  # noqa: ARG005
    ("anything, object", lambda m: {m.anything: int, object: str}),
    ("lax(int), int", lambda m: {m.lax(int): int, int: str}),
    ("strict(int), int", lambda m: {m.strict(int): int, int: str}),
    (
        "complement, complement",
        lambda m: {m.complement(int): int, m.complement(m.union(int)): str},
    ),
    ("regex, regex", lambda m: {m.regex("a"): int, m.regex("a"): str}),
    ("a field and a clause", lambda m: {"a": int, m.union("a"): str}),
    ("a field and Literal", lambda m: {"a": int, typing.Literal["a"]: str}),  # noqa: ARG005
    (
        "two Literals",
        lambda m: {typing.Literal["a"]: int, m.union(typing.Literal["a"]): str},
    ),
    ("three kinds", lambda m: {object: int, typing.Any: str, m.anything: bytes}),
]

# Each schema form vtjson reads without a construct.
FORMS: list[tuple[str, object]] = [
    # A class is an instance check, whichever kind it is.
    *(
        (cls.__name__, cls)
        for cls in (
            object,
            int,
            bool,
            float,
            complex,
            str,
            bytes,
            bytearray,
            list,
            tuple,
            dict,
            set,
            frozenset,
            type,
            range,
            decimal.Decimal,
            fractions.Fraction,
            dt.date,
            dt.datetime,
            dt.time,
            re.Pattern,
            pathlib.PurePath,
            Exception,
            _Plain,
            _Data,
            _Pair,
            _Color,
            _Attributes,
            _Hinted,
            _HintedDict,
            _Unhinted,
            OrderedDict,
            defaultdict,
            UserDict,
            UserList,
            deque,
        )
    ),
    ("None", None),
    ("Any", typing.Any),
    ("NoneType", type(None)),
    # Containers, at each arity and with each reading of `...`.
    ("[]", []),
    ("[int]", [int]),
    ("[int, str]", [int, str]),
    ("[int, ...]", [int, ...]),
    ("[int, str, ...]", [int, str, ...]),
    ("[...]", [...]),
    ("[..., int]", [..., int]),
    ("[..., ...]", [..., ...]),
    ("[int, ..., str]", [int, ..., str]),
    ("[int, ..., str, ...]", [int, ..., str, ...]),
    ("()", ()),
    ("(int,)", (int,)),
    ("(int, str)", (int, str)),
    ("(int, ...)", (int, ...)),
    ("(int, str, ...)", (int, str, ...)),
    ("(...,)", (...,)),
    ("(..., int)", (..., int)),
    ("(..., ...)", (..., ...)),
    ("(int, ..., str)", (int, ..., str)),
    ("set()", set()),
    ("{int}", {int}),
    ("{int, str}", {int, str}),
    ("frozenset({int})", frozenset({int})),
    ("{}", {}),
    # Each spelling of a key, and each key kind beside another.
    ("{'a': int}", {"a": int}),
    ("{'a?': int}", {"a?": int}),
    ("{'a\\\\?': int}", {"a\\?": int}),
    ("{'a': int, 'b': int}", {"a": int, "b": int}),
    ("{'a': int, 'b?': str}", {"a": int, "b?": str}),
    ("{str: int}", {str: int}),
    ("{int: str}", {int: str}),
    ("{object: object}", {object: object}),
    ("{'a': str, str: int}", {"a": str, str: int}),
    # A constant key's cross-type equals are the ledger's typed singletons, so no
    # row writes one a value in `VALUES` equals across types.
    ("{1: str}", {1: str}),
    ("{None: int}", {None: int}),
    ("{(1,): int}", {(1,): int}),
    ("{1.5: int}", {1.5: int}),
    ("{'': int}", {"": int}),
    ("{b'a': int}", {b"a": int}),
    ("{frozenset({int}): int}", {frozenset({int}): int}),
    ("{(int, str): int}", {(int, str): int}),
    ("{int | None: int}", {int | None: int}),
    ("{Optional[int]: int}", {typing.Optional[int]: int}),  # noqa: UP045
    ("{Union[int, str]: int}", {typing.Union[int, str]: int}),  # noqa: UP007
    ("{Literal['a']: int}", {typing.Literal["a"]: int}),
    ("{list[int]: int}", {list[int]: int}),
    ("{Any: int}", {typing.Any: int}),
    ("{object: int, 'a': str}", {object: int, "a": str}),
    # Containers written in other classes.
    ("OrderedDict", OrderedDict(a=int)),
    ("defaultdict", defaultdict(int, {"a": int})),
    ("UserDict", UserDict(a=int)),
    ("UserList", UserList([int])),
    ("deque", deque([int])),
    ("_Pair(int, str)", _PAIR_OF_TYPES),
    # Subscripted generics.
    ("list[int]", list[int]),
    ("tuple[int, ...]", tuple[int, ...]),
    ("tuple[int, str]", tuple[int, str]),
    ("tuple[()]", tuple[()]),
    ("tuple[int]", tuple[int]),
    ("tuple[int, str, bytes]", tuple[int, str, bytes]),
    ("tuple[...]", tuple[...]),  # ty: ignore[invalid-type-form]
    ("tuple[..., int]", tuple[..., int]),  # ty: ignore[invalid-type-form]
    ("tuple[int, ..., str]", tuple[int, ..., str]),  # ty: ignore[invalid-type-form]
    ("typing.Tuple[int, str]", typing.Tuple[int, str]),  # noqa: UP006
    ("set[int]", set[int]),
    ("frozenset[int]", frozenset[int]),
    ("dict[str, int]", dict[str, int]),
    ("typing.List[int]", typing.List[int]),  # noqa: UP006
    ("typing.Dict[str, int]", typing.Dict[str, int]),  # noqa: UP006
    ("typing.Tuple[int, ...]", typing.Tuple[int, ...]),  # noqa: UP006
    ("typing.Set[int]", typing.Set[int]),  # noqa: UP006
    ("Sequence[int]", typing.Sequence[int]),
    ("Mapping[str, int]", typing.Mapping[str, int]),
    ("Optional[int]", typing.Optional[int]),  # noqa: UP045
    ("Union[int, str]", typing.Union[int, str]),  # noqa: UP007
    ("int | str", int | str),
    ("int | None", int | None),
    ("Literal['a']", typing.Literal["a"]),
    ("Literal['a', 'b']", typing.Literal["a", "b"]),
    ("Literal[None]", typing.Literal[None]),  # noqa: PYI061
    ("Annotated[int, object]", typing.Annotated[int, object]),
    ("Annotated[int, str]", typing.Annotated[int, str]),
    ("NewType", _Named),
    # A callable is a predicate over any value, whatever kind of callable.
    ("a function", _is_truthy),
    ("a raising function", _length),
    ("a builtin", callable),
    ("a method", "a".__eq__),
    ("a bound class method", dict.fromkeys),
]

# Each constant, whose cross-type equals `docs/03-conformance.md` ledgers.
CONSTANTS: list[object] = [
    0,
    1,
    True,
    False,
    1.0,
    1.5,
    math.inf,
    math.nan,
    1j,
    "",
    "a",
    b"a",
    bytearray(b"a"),
    decimal.Decimal("1.5"),
    fractions.Fraction(1, 2),
    dt.date(2024, 1, 31),
    _Color.RED,
    Ellipsis,
    NotImplemented,
]

# Where a schema can sit, and the value that reaches it there.
_POSITIONS: list[tuple[str, Callable[[Any, Any], object], Callable[[Any], object]]] = [
    ("a list element", lambda m, s: [s, ...], lambda v: [v]),  # noqa: ARG005
    ("a fixed element", lambda m, s: [s], lambda v: [v]),  # noqa: ARG005
    ("a tuple element", lambda m, s: (s,), lambda v: (v,)),  # noqa: ARG005
    ("a set member", lambda m, s: {s}, lambda v: {v}),  # noqa: ARG005
    ("a field", lambda m, s: {"k": s}, lambda v: {"k": v}),  # noqa: ARG005
    ("an optional field", lambda m, s: {"k?": s}, lambda v: {"k": v}),  # noqa: ARG005
    (
        "an optional_key field",
        lambda m, s: {m.optional_key("k"): s},
        lambda v: {"k": v},
    ),
    ("a key", lambda m, s: {s: object}, lambda v: {v: 1}),  # noqa: ARG005
    ("list[...]", lambda m, s: list[s], lambda v: [v]),  # noqa: ARG005
    ("tuple[..., ...]", lambda m, s: tuple[s, ...], lambda v: (v,)),  # noqa: ARG005
    ("set[...]", lambda m, s: set[s], lambda v: {v}),  # noqa: ARG005
    ("dict[str, ...]", lambda m, s: dict[str, s], lambda v: {"k": v}),  # noqa: ARG005
    ("Optional[...]", lambda m, s: typing.Optional[s], lambda v: v),  # noqa: ARG005, UP045
    ("Annotated metadata", lambda m, s: typing.Annotated[object, s], lambda v: v),  # noqa: ARG005
    ("Annotated base", lambda m, s: typing.Annotated[s, object], lambda v: v),  # noqa: ARG005
    ("a union arm", lambda m, s: m.union(s, None), lambda v: v),
    ("an intersect member", lambda m, s: m.intersect(s, object), lambda v: v),
    ("a complement", lambda m, s: m.complement(s), lambda v: v),
    ("an ifthen condition", lambda m, s: m.ifthen(s, object, str), lambda v: v),
    ("an ifthen branch", lambda m, s: m.ifthen(object, s), lambda v: v),
    ("a cond branch", lambda m, s: m.cond((object, s)), lambda v: v),
    ("lax", lambda m, s: m.lax(s), lambda v: v),
    ("strict", lambda m, s: m.strict(s), lambda v: v),
    ("set_name", lambda m, s: m.set_name(s, "named"), lambda v: v),
    ("set_label", lambda m, s: m.set_label(s, "label"), lambda v: v),
    ("filter", lambda m, s: m.filter(_identity, s), lambda v: v),
    ("fields", lambda m, s: m.fields({"x": s}), _Attributes),
]


def _lifted(lift: Callable[[Any], object]) -> list[object]:
    """Return every value lifted to a position, but those it cannot hold."""
    lifted = []
    for value in VALUES:
        try:
            lifted.append(lift(value))
        except TypeError:
            continue
    return lifted


POSITIONS = [(label, build, _lifted(lift)) for label, build, lift in _POSITIONS]


@dataclass(frozen=True)
class _Entry:
    """A way of asking the oracle's question, and the parameters it passes."""

    label: str
    prepare: Callable[[Any, object], object]
    ask: Callable[[Any, Any, object], object]
    parameters: frozenset[str]


def _as_given(_module: Any, schema: object) -> object:
    return schema


def _compiled(module: Any, schema: object) -> object:
    return module.compile(schema)


def _cast_gives_the_object(module: Any, schema: object, obj: object) -> None:
    assert module.safe_cast(schema, obj) is obj


def _instance_of_type(_module: Any, made: Any, obj: object) -> None:
    if not isinstance(obj, made):
        raise _NotInstanceError


class _NotInstanceError(Exception):
    """`isinstance` answered `False`, which is `make_type`'s refusal."""


def _entry(
    label: str,
    prepare: Callable[[Any, object], object],
    ask: Callable[[Any, Any, object], object],
    *parameters: str,
) -> _Entry:
    return _Entry(label, prepare, ask, frozenset(parameters))


def _made(**kwargs: object) -> Callable[[Any, object], object]:
    return lambda m, s: m.make_type(s, **kwargs)


ENTRIES: list[_Entry] = [
    _entry(
        "validate(schema, obj)",
        _as_given,
        lambda m, s, o: m.validate(s, o),
        "validate:schema",
        "validate:obj",
    ),
    _entry(
        "validate(schema=, obj=)",
        _as_given,
        lambda m, s, o: m.validate(schema=s, obj=o),
    ),
    _entry(
        "validate(schema, obj, name)",
        _as_given,
        lambda m, s, o: m.validate(s, o, "named"),
        "validate:name",
    ),
    _entry(
        "validate(schema, obj, name, strict)",
        _as_given,
        lambda m, s, o: m.validate(s, o, "named", False),
        "validate:strict",
    ),
    _entry(
        "validate(strict=True)",
        _as_given,
        lambda m, s, o: m.validate(s, o, strict=True),
    ),
    _entry(
        "validate(strict=False)",
        _as_given,
        lambda m, s, o: m.validate(s, o, strict=False),
    ),
    _entry(
        "validate(subs={})",
        _as_given,
        lambda m, s, o: m.validate(s, o, subs={}),
        "validate:subs",
    ),
    _entry(
        "validate(compile(schema), obj)",
        _compiled,
        lambda m, s, o: m.validate(s, o),
        "compile:schema",
    ),
    _entry(
        "validate(compile(schema), obj, strict=False)",
        _compiled,
        lambda m, s, o: m.validate(s, o, strict=False),
    ),
    _entry(
        "validate(compile(compile(schema)), obj)",
        lambda m, s: m.compile(m.compile(s)),
        lambda m, s, o: m.validate(s, o),
    ),
    _entry(
        "validate({'k': compile(schema)}, obj)",
        lambda m, s: {"k": m.compile(s)},
        lambda m, s, o: m.validate(s, {"k": o}),
    ),
    _entry(
        "safe_cast(schema, obj)",
        _as_given,
        _cast_gives_the_object,
        "safe_cast:schema",
        "safe_cast:obj",
    ),
    _entry(
        "isinstance(obj, make_type(schema))",
        _made(),
        _instance_of_type,
        "make_type:schema",
    ),
    _entry(
        "isinstance(obj, make_type(schema, 'named'))",
        _made(name="named"),
        _instance_of_type,
        "make_type:name",
    ),
    _entry(
        "isinstance(obj, make_type(schema, strict=False))",
        _made(strict=False),
        _instance_of_type,
        "make_type:strict",
    ),
    _entry(
        "isinstance(obj, make_type(schema, debug=True))",
        _made(debug=True),
        _instance_of_type,
        "make_type:debug",
    ),
    _entry(
        "isinstance(obj, make_type(schema, subs={}))",
        _made(subs={}),
        _instance_of_type,
        "make_type:subs",
    ),
    _entry(
        "validate(make_type(schema), obj)",
        _made(),
        lambda m, s, o: m.validate(s, o),
    ),
]

# What each parameter is given when another is the one under test, so that a
# call fails only for the argument being swept.
_VALID: dict[str, tuple[object, ...]] = {
    "ge": (0,),
    "gt": (0,),
    "le": (0,),
    "lt": (0,),
    "interval": (0, 1),
    "size": (1,),
    "div": (2,),
    "close_to": (1.5,),
    "regex": ("a",),
    "glob": ("*.py",),
    "magic": ("text/plain",),
    "fields": ({"x": int},),
    "filter": (_length, int),
    "complement": (int,),
    "ifthen": (int, str),
    "lax": (int,),
    "strict": (int,),
    "quote": (1,),
    "set_name": (int, "named"),
    "set_label": (int, "label"),
    "protocol": (_Hinted,),
    "optional_key": ("a",),
}

# What a caller might pass by mistake, or on purpose where a parameter takes more
# than its annotation says.
_JUNK: list[object] = [
    None,
    True,
    False,
    0,
    1,
    -1,
    1.5,
    math.nan,
    "",
    "a",
    b"a",
    [],
    [int],
    (),
    (int,),
    {},
    {"a": int},
    set(),
    int,
    object,
    _length,
    ...,
]


# A parameter a schema is written in. A number there is a constant, whose
# cross-type equals `test_a_constant_decides_as_the_oracle_does` owns.
_SCHEMA_VALUED = frozenset(
    {"schema", "schemas", "if_schema", "then_schema", "else_schema"}
)


def _junk_for(parameter: inspect.Parameter) -> list[object]:
    if parameter.name not in _SCHEMA_VALUED:
        return _JUNK
    return [junk for junk in _JUNK if not isinstance(junk, int | float)]


def _junk_calls() -> list[_Call]:
    """Return each construct with one parameter at each junk value."""
    calls = []
    for name in sorted({call.name for call in CALLS} | {"optional_key"}):
        parameters = inspect.signature(getattr(vt, name)).parameters.values()
        valid = _VALID.get(name, ())
        named = [p for p in parameters if p.kind is p.POSITIONAL_OR_KEYWORD]
        for parameter in parameters:
            for junk in _junk_for(parameter):
                if parameter.kind is parameter.VAR_POSITIONAL:
                    calls.append(_Call(name, (*valid[: len(named)], junk)))
                elif parameter.kind is parameter.VAR_KEYWORD:
                    calls.append(_Call(name, valid, {"check_deliverability": junk}))
                elif parameter in named and named.index(parameter) < len(valid):
                    at = named.index(parameter)
                    calls.append(_Call(name, (*valid[:at], junk, *valid[at + 1 :])))
                else:
                    calls.append(_Call(name, valid, {parameter.name: junk}))
    return calls


def _fake_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer every DNS question here, so a row asking one is deterministic."""
    resolver = pytest.importorskip("dns.resolver")

    def resolve(_self: object, name: object, *_a: object, **_k: object) -> list[str]:
        if str(name).rstrip(".") == "example.com":
            return []
        raise resolver.NXDOMAIN

    monkeypatch.setattr(resolver.Resolver, "resolve", resolve)


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_resolution(monkeypatch)


def _refusal(module: Any, exc: Exception) -> str:
    """Return the outcome ``exc`` stands for under ``module``."""
    if isinstance(exc, module.SchemaError):
        return "schema-error"
    if isinstance(exc, (module.ValidationError, _NotInstanceError)):
        return "reject"
    return f"raises {type(exc).__name__}"


def _column(
    module: Any,
    build: Callable[[Any], object],
    objects: list[object],
    entry: _Entry,
) -> list[str]:
    """Return ``module``'s outcome on each object, the same one if none is reached."""
    try:
        prepared = entry.prepare(module, build(module))
    except Exception as exc:  # noqa: BLE001  (the refusal is the answer compared)
        return [_refusal(module, exc)] * len(objects)
    outcomes = []
    for obj in objects:
        try:
            entry.ask(module, prepared, obj)
        except Exception as exc:  # noqa: BLE001  (the refusal is the answer compared)
            outcomes.append(_refusal(module, exc))
        else:
            outcomes.append("accept")
    return outcomes


def _agree(oracle: str, layer: str, *, nested: bool = False) -> bool:
    """Whether two outcomes are one answer, or a difference the ledger records.

    `docs/03-conformance.md` records one direction: a rejection where vtjson's
    `validate` lets an exception out, and never the other way round. Nested, that
    rejection is the part's, and what holds it decides from there: a `complement`
    admits what its part rejected, and a union goes on to its next arm.
    """
    if oracle == layer:
        return True
    if not oracle.startswith("raises "):
        return False
    return layer == "reject" or (nested and layer == "accept")


def _divergences(
    build: Callable[[Any], object],
    objects: list[object],
    entry: _Entry | None = None,
    *,
    nested: bool = False,
) -> list[str]:
    """Return one line per object the two libraries answer apart."""
    entry = entry or _ONE_COMPILE
    return [
        f"{obj!r:.60} vtjson={a} layer={b}"
        for obj, a, b in zip(
            objects,
            _column(vt, build, objects, entry),
            _column(vg, build, objects, entry),
            strict=True,
        )
        if not _agree(a, b, nested=nested)
    ]


_ONE_COMPILE = _entry(
    "validate(compile(schema), obj)", _compiled, lambda m, s, o: m.validate(s, o)
)


def _report(lines: list[str]) -> str:
    return "\n".join(lines)


@pytest.mark.parametrize("call", CALLS, ids=lambda c: c.label)
def test_each_call_decides_as_the_oracle_does(call: _Call) -> None:
    """Each argument a construct takes selects the set vtjson selects."""
    assert not (lines := _divergences(call.build, VALUES)), _report(lines)


@pytest.mark.parametrize("name", NULLARY)
def test_a_nullary_construct_reads_alike_bare_and_called(name: str) -> None:
    """A construct taking nothing is a schema written with or without its call."""
    bare = _divergences(lambda m: getattr(m, name), VALUES)
    called = _divergences(lambda m: getattr(m, name)(), VALUES)
    assert not bare, _report(bare)
    assert not called, _report(called)


@pytest.mark.parametrize(
    "name", sorted({c.name for c in CALLS} - set(NULLARY) | {"optional_key"})
)
def test_a_construct_needing_arguments_is_read_alike_bare(name: str) -> None:
    """A construct written without the arguments it needs, as a schema."""
    assert not (lines := _divergences(lambda m: getattr(m, name), VALUES)), _report(
        lines
    )


@pytest.mark.parametrize(
    ("call", "build"), KEYED, ids=[f"{i}-{k[0].label}" for i, k in enumerate(KEYED)]
)
def test_an_optional_key_decides_as_the_oracle_does(
    call: _Call, build: Callable[[Any], object]
) -> None:
    """A key marked optional, however it is marked."""
    del call
    assert not (lines := _divergences(build, VALUES)), _report(lines)


_KEYED_VALUES: list[object] = [
    {},
    {1: "a"},
    {1: b"a"},
    {1: 1},
    {"a": 1},
    {"a": "b"},
    {"a": b"b"},
    {"b": 1},
    {"b": "b"},
    {None: 1},
    {None: True},
    {1.5: 1},
    {1.5: "a"},
    {(1,): 1},
    {b"a": 1},
    {1: "a", "a": 1},
    {"aa": 1},
]


@pytest.mark.parametrize("mode", ["alone", "lax"])
@pytest.mark.parametrize(("label", "build"), KEYS_ALIKE, ids=[k[0] for k in KEYS_ALIKE])
def test_keys_building_one_validator_stay_two_clauses(
    label: str, build: Callable[[Any], object], mode: str
) -> None:
    """A key any clause claiming it admits belongs, whichever clause that is."""
    del label

    def schema(m: Any) -> object:
        return m.lax(build(m)) if mode == "lax" else build(m)

    assert not (lines := _divergences(schema, _KEYED_VALUES)), _report(lines)


@pytest.mark.parametrize(
    "keys",
    [
        lambda m: (m.ge(0), m.ge(0)),
        lambda m: (m.ge(0), m.interval(0, ...)),
        lambda m: (m.size(1), m.size(1, 1)),
    ],
    ids=["ge(0), ge(0)", "ge(0), interval(0, ...)", "size(1), size(1, 1)"],
)
def test_keys_comparing_equal_are_the_ledgered_collapse(
    keys: Callable[[Any], tuple[object, object]],
) -> None:
    """The caller's own dict holds one key where it holds two under vtjson.

    A valgebra validator compares by the set it denotes, and a vtjson construct
    by its identity, so Python keeps one of two keys that denote one set before
    either library reads the dict.
    """
    assert len(dict.fromkeys(keys(vt))) == 2
    assert len(dict.fromkeys(keys(vg))) == 1
    assert "compare equal" in _LEDGER


@pytest.mark.parametrize(("label", "schema"), FORMS, ids=[f[0] for f in FORMS])
def test_each_form_decides_as_the_oracle_does(label: str, schema: object) -> None:
    """A schema written without a construct, read by what it is."""
    del label
    assert not (lines := _divergences(lambda m: schema, VALUES)), _report(lines)  # noqa: ARG005


@pytest.mark.parametrize("constant", CONSTANTS, ids=repr)
def test_a_constant_decides_as_the_oracle_does(constant: object) -> None:
    """A constant matches itself, but for the cross-type equals the ledger records."""
    objects = [
        obj
        for obj in VALUES
        if type(obj) is type(constant) or not _equal(obj, constant)
    ]
    assert not (lines := _divergences(lambda m: constant, objects)), _report(lines)  # noqa: ARG005


def _equal(left: object, right: object) -> bool:
    try:
        return bool(left == right)
    except Exception:  # noqa: BLE001  (a value that cannot answer is not equal)
        return False


# A schema refused where it stands is refused wherever it sits, and the first
# rows already compare that, so a position asks only what builds.
def _builds(call: _Call) -> bool:
    try:
        vt.compile(call.build(vt))
    except Exception:  # noqa: BLE001  (any refusal is not building)
        return False
    return True


_BUILDING = [call for call in CALLS if _builds(call)]


@pytest.mark.parametrize("position", POSITIONS, ids=[p[0] for p in POSITIONS])
@pytest.mark.parametrize("call", _BUILDING, ids=lambda c: c.label)
def test_a_call_decides_alike_wherever_it_sits(
    call: _Call,
    position: tuple[str, Callable[[Any, Any], object], list[object]],
) -> None:
    """A construct is the same set inside any schema, as it is alone."""
    _, place, objects = position
    lines = _divergences(lambda m: place(m, call.build(m)), objects, nested=True)
    assert not lines, _report(lines)


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.label)
@pytest.mark.parametrize("call", _BUILDING, ids=lambda c: c.label)
def test_a_call_decides_alike_however_it_is_asked(call: _Call, entry: _Entry) -> None:
    """Every entry point reaches the verdict vtjson's does."""
    lines = _divergences(call.build, VALUES, entry)
    assert not lines, _report(lines)


@pytest.mark.parametrize("call", _junk_calls(), ids=lambda c: c.label)
def test_a_call_at_any_argument_decides_as_the_oracle_does(call: _Call) -> None:
    """A construct takes what vtjson's takes, and refuses what vtjson's refuses."""
    assert not (lines := _divergences(call.build, VALUES)), _report(lines)


@pytest.mark.parametrize("position", POSITIONS, ids=[p[0] for p in POSITIONS])
@pytest.mark.parametrize(("label", "schema"), FORMS, ids=[f[0] for f in FORMS])
def test_a_form_decides_alike_wherever_it_sits(
    label: str,
    schema: object,
    position: tuple[str, Callable[[Any, Any], object], list[object]],
) -> None:
    """A schema written without a construct is one set inside any schema."""
    del label
    _, place, objects = position
    lines = _divergences(lambda m: place(m, schema), objects, nested=True)
    assert not lines, _report(lines)


@pytest.mark.parametrize("entry", ENTRIES, ids=lambda e: e.label)
@pytest.mark.parametrize(("label", "schema"), FORMS, ids=[f[0] for f in FORMS])
def test_a_form_decides_alike_however_it_is_asked(
    label: str, schema: object, entry: _Entry
) -> None:
    """Every entry point reads a schema written without a construct alike."""
    del label
    lines = _divergences(lambda m: schema, VALUES, entry)  # noqa: ARG005
    assert not lines, _report(lines)


# An entry point's argument other than the schema and the value, at each junk
# value, over a schema where the mode decides and one where it does not.
_ENTRY_ARGUMENTS: list[tuple[str, Callable[[Any, object], object]]] = [
    ("validate(name=)", lambda m, j: lambda s, o: m.validate(s, o, name=j)),
    ("validate(strict=)", lambda m, j: lambda s, o: m.validate(s, o, strict=j)),
    (
        "make_type(name=)",
        lambda m, j: lambda s, o: _instance_of_type(m, m.make_type(s, name=j), o),
    ),
    (
        "make_type(strict=)",
        lambda m, j: lambda s, o: _instance_of_type(m, m.make_type(s, strict=j), o),
    ),
    (
        "make_type(debug=)",
        lambda m, j: lambda s, o: _instance_of_type(m, m.make_type(s, debug=j), o),
    ),
]


@pytest.mark.parametrize("junk", _JUNK, ids=_spelled)
@pytest.mark.parametrize("schema", [int, {"a": int}], ids=["int", "a record"])
@pytest.mark.parametrize(
    ("label", "asker"), _ENTRY_ARGUMENTS, ids=[a[0] for a in _ENTRY_ARGUMENTS]
)
def test_an_entry_point_takes_what_the_oracle_takes(
    label: str,
    asker: Callable[[Any, object], Any],
    schema: object,
    junk: object,
) -> None:
    """An argument that decides nothing here decides nothing there either."""
    del label
    entry = _entry(
        "asked",
        lambda m, s: (asker(m, junk), s),
        lambda m, prepared, o: prepared[0](prepared[1], o),  # noqa: ARG005
    )
    objects: list[object] = [1, "a", {"a": 1}, {"a": 1, "b": 2}, {"a": "x"}, None]
    assert not (lines := _divergences(lambda m: schema, objects, entry)), _report(lines)  # noqa: ARG005


@pytest.mark.parametrize(
    ("schema", "kwargs"),
    [
        (int, {}),
        (str, {}),
        (_Plain, {}),
        (_is_truthy, {}),
        ({"a": int}, {}),
        ([int], {}),
        (None, {}),
        ("a", {}),
        (1, {}),
        (int, {"name": "named"}),
        ({"a": int}, {"name": "named"}),
    ],
    ids=_spelled,
)
def test_a_made_type_is_named_as_the_oracle_names_it(
    schema: object, kwargs: dict[str, Any]
) -> None:
    """The name given, or the schema's own, or vtjson's word for one it lacks."""
    reference, layer = vt.make_type(schema, **kwargs), vg.make_type(schema, **kwargs)
    assert layer.__name__ == reference.__name__
    assert isinstance(reference, type)
    assert isinstance(layer, type)


def _key_answers(module: Any) -> list[object]:
    """Return what a caller can read off an `optional_key`."""
    key = module.optional_key("a")
    required = module.optional_key("a", _optional=False)
    return [
        key.key,
        key.optional,
        required.key,
        required.optional,
        key == module.optional_key("a"),
        key == required,
        key == "a",
        key != "a",
        hash(key) == hash(module.optional_key("a")),
        hash(key) == hash(required),
        hash(key) == hash("a"),
    ]


def test_an_optional_key_answers_as_the_oracle_s_does() -> None:
    """Its attributes, its equality and its hash, which a mapping key depends on."""
    assert _key_answers(vg) == _key_answers(vt)


@pytest.mark.parametrize("name", ["SchemaError", "ValidationError"])
def test_each_error_class_is_an_exception_of_its_own(name: str) -> None:
    """A caller catches one without the other, in both libraries."""
    for module in (vt, vg):
        error: Any = getattr(module, name)
        other = module.ValidationError if name == "SchemaError" else module.SchemaError
        assert issubclass(error, Exception)
        assert not issubclass(error, other)
        assert not issubclass(other, error)
        assert not issubclass(error, (TypeError, KeyError, AttributeError))


def test_a_schema_error_carries_its_message() -> None:
    """`SchemaError` is raised by a caller's own code as well as by the library."""
    assert str(vg.SchemaError("bad")) == str(vt.SchemaError("bad"))


@pytest.mark.parametrize(
    "ask",
    [
        lambda m: m.validate(m.set_label(int, "label"), "a", subs={"label": str}),
        lambda m: isinstance("a", m.make_type(m.set_label(int, "l"), subs={"l": str})),
    ],
    ids=["validate", "make_type"],
)
def test_a_substitution_is_the_ledgered_refusal(ask: Callable[[Any], object]) -> None:
    """Vtjson performs it, and the layer refuses rather than ignores it."""
    ask(vt)
    with pytest.raises(NotImplementedError):
        ask(vg)


@pytest.mark.parametrize("name", ["Apply", "skip_first", "compiled_schema", "wrapper"])
def test_a_name_the_ledger_records_as_unsupported_is_absent(name: str) -> None:
    """An attribute that does not exist fails where it is written, not on a value."""
    assert hasattr(vt, name)
    assert not hasattr(vg, name)
    assert name in _LEDGER


# The names vtjson defines itself, which a caller writes a schema or a check with.
_OWN = frozenset(
    name
    for name in dir(vt)
    if not name.startswith("_")
    and getattr(getattr(vt, name), "__module__", None) == vt.validate.__module__
)
_ENTRY_POINTS = frozenset({"validate", "compile", "make_type", "safe_cast"})
_ERRORS = frozenset({"SchemaError", "ValidationError"})
_LEDGERED = frozenset({"Apply", "skip_first", "compiled_schema", "wrapper"})
# What vtjson annotates its own signatures with, and no call takes.
_ANNOTATION_ONLY = frozenset({"C", "K", "StringKeyType", "T", "comparable"})


def test_every_public_name_is_swept() -> None:
    """A name vtjson adds fails here until a row reaches it."""
    swept = {call.name for call in CALLS} | {k[0].name for k in KEYED} | set(NULLARY)
    placed = swept | _ENTRY_POINTS | _ERRORS | _LEDGERED | _ANNOTATION_ONLY
    assert not (unswept := sorted(_OWN - placed)), f"no row reaches {unswept}"
    assert not (stale := sorted(placed - _OWN)), f"vtjson has no name {stale}"


def _bound_parameters(call: _Call) -> set[tuple[str, str]]:
    """Return each parameter ``call`` passes an argument to."""
    signature = inspect.signature(getattr(vt, call.name))
    try:
        bound = signature.bind(*call.args, **call.kwargs)
    except TypeError:
        return set()
    return {(call.name, parameter) for parameter in bound.arguments}


def test_every_parameter_is_swept() -> None:
    """A parameter vtjson adds fails here until a hand-written row passes it."""
    passed = {
        parameter
        for call in (*CALLS, *(k[0] for k in KEYED))
        for parameter in _bound_parameters(call)
    }
    for entry in ENTRIES:
        for parameter in entry.parameters:
            name, argument = parameter.split(":")
            passed.add((name, argument))
    declared = {
        (name, parameter)
        for name in sorted(_OWN - _LEDGERED - _ERRORS - _ANNOTATION_ONLY)
        for parameter in inspect.signature(getattr(vt, name)).parameters
    }
    assert not (unswept := sorted(declared - passed)), f"no row passes {unswept}"
