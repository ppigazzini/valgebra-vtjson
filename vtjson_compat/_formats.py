"""vtjson string-format and network-format validators.

The string formats use the same standard-library engines vtjson uses (``re``,
``pathlib``, ``urllib``, ``datetime``, ``ipaddress``); parity requires the same
engine, since a different regular-expression implementation would accept a
different dialect. The network formats (``email``, ``domain_name``, ``magic``)
reuse the same third-party packages vtjson does and are imported lazily as
optional extras.
"""

import datetime
import ipaddress
import pathlib
import re
from urllib.parse import urlparse

from ._translate import _nullary, _predicate, _require
from ._valgebra_api import CompiledValidator


def regex(
    pattern: str,
    name: str | None = None,
    fullmatch: bool = True,  # noqa: FBT001, FBT002
    flags: int = 0,
) -> CompiledValidator:
    """Match strings against a regular expression (full match by default)."""
    del name  # accepted for vtjson signature parity; unused
    compiled = re.compile(pattern, flags)
    match = compiled.fullmatch if fullmatch else compiled.match
    return _predicate(lambda obj: isinstance(obj, str) and match(obj) is not None)


@_nullary
def regex_pattern() -> CompiledValidator:
    """Match strings that are themselves valid regular expressions."""

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        try:
            re.compile(obj)
        except re.error:
            return False
        return True

    return _predicate(check)


def glob(pattern: str, name: str | None = None) -> CompiledValidator:
    """Match strings against a Unix filename pattern (``PurePath.match``)."""
    del name  # accepted for vtjson signature parity; unused

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        try:
            return pathlib.PurePath(obj).match(pattern)
        except (ValueError, TypeError):
            return False

    return _predicate(check)


@_nullary
def url() -> CompiledValidator:
    """Match strings parseable as a URL with a scheme and a network location."""

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        result = urlparse(obj)
        return bool(result.scheme and result.netloc)

    return _predicate(check)


@_nullary
def ip_address(version: int | None = None) -> CompiledValidator:
    """Match IP addresses of the given version (4, 6, or any)."""
    if version == 4:  # noqa: PLR2004
        method = ipaddress.IPv4Address
    elif version == 6:  # noqa: PLR2004
        method = ipaddress.IPv6Address
    elif version is None:
        method = ipaddress.ip_address
    else:
        msg = "version is not 4 or 6"
        raise ValueError(msg)

    def check(obj: object) -> bool:
        if not isinstance(obj, int | str | bytes):
            return False
        try:
            method(obj)
        except (ValueError, ipaddress.AddressValueError):
            return False
        return True

    return _predicate(check)


@_nullary
def date_time(format: str | None = None) -> CompiledValidator:  # noqa: A002
    """Match an ISO 8601 date-time, or a ``strptime`` ``format`` if given."""

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        try:
            if format is not None:
                datetime.datetime.strptime(obj, format)  # noqa: DTZ007
            else:
                datetime.datetime.fromisoformat(obj)
        except (ValueError, TypeError):
            return False
        return True

    return _predicate(check)


@_nullary
def date() -> CompiledValidator:
    """Match an ISO 8601 date."""

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        try:
            datetime.date.fromisoformat(obj)
        except (ValueError, TypeError):
            return False
        return True

    return _predicate(check)


@_nullary
def time() -> CompiledValidator:
    """Match an ISO 8601 time."""

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        try:
            datetime.time.fromisoformat(obj)
        except (ValueError, TypeError):
            return False
        return True

    return _predicate(check)


@_nullary
def email(**kw: object) -> CompiledValidator:
    """Match valid email addresses (via ``email_validator``, like vtjson)."""
    email_validator = _require("email_validator")
    kw.setdefault("check_deliverability", False)

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        try:
            email_validator.validate_email(obj, **kw)  # ty: ignore[unresolved-attribute]
        except Exception:  # noqa: BLE001  (any rejection means non-member)
            return False
        return True

    return _predicate(check)


@_nullary
def domain_name(
    ascii_only: bool = True,  # noqa: FBT001, FBT002
    resolve: bool = False,  # noqa: FBT001, FBT002
) -> CompiledValidator:
    """Match valid domain names (via ``idna``, like vtjson).

    With ``ascii_only=False`` IDNA names are allowed; ``resolve=True`` also
    checks that the name resolves (needs ``dnspython``).
    """
    idna = _require("idna")
    resolver = _require("dns.resolver") if resolve else None
    ascii_re = re.compile(r"[\x00-\x7F]*")

    def check(obj: object) -> bool:
        if not isinstance(obj, str):
            return False
        if ascii_only and not ascii_re.fullmatch(obj):
            return False
        try:
            idna.encode(obj, uts46=False)  # ty: ignore[unresolved-attribute]
        except idna.core.IDNAError:  # ty: ignore[unresolved-attribute]
            return False
        if resolve:
            try:
                resolver.resolve(obj)  # ty: ignore[unresolved-attribute]
            except Exception:  # noqa: BLE001  (an unresolvable name is a non-member)
                return False
        return True

    return _predicate(check)


def magic(mime_type: str, name: str | None = None) -> CompiledValidator:
    """Match a buffer whose libmagic MIME type equals ``mime_type``.

    Needs the optional ``python-magic`` package (and the system libmagic
    library); install it with ``pip install valgebra-vtjson[magic]``.
    """
    detector = _require("magic")
    del name

    def check(obj: object) -> bool:
        if not isinstance(obj, str | bytes):
            return False
        try:
            detected = detector.from_buffer(obj, mime=True)  # ty: ignore[unresolved-attribute]
        except Exception:  # noqa: BLE001  (any detection failure means non-member)
            return False
        return detected == mime_type

    return _predicate(check)
