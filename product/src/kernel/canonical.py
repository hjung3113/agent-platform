"""Deterministic canonical JSON serialization and content digests.

Canonical artifact identity is a Kernel concern shared by producers and
validators, so this module is intentionally small and dependency-free.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CANONICAL_FORMAT = "agent-platform-json-v1"
DIGEST_ALGORITHM = "sha256"
MAX_SAFE_INTEGER = (1 << 53) - 1
MIN_SAFE_INTEGER = -MAX_SAFE_INTEGER
MAX_NESTING_DEPTH = 256
_DIGEST_DOMAIN = CANONICAL_FORMAT.encode("ascii") + b"\x00"


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the canonical format."""


def _validate_string(value: str, path: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalizationError(f"invalid Unicode string at {path}") from exc


def _utf16_sort_key(value: str) -> bytes:
    """Return the language-neutral v1 object-key ordering key."""

    return value.encode("utf-16-be")


def _prepare(
    value: Any,
    path: str = "$",
    depth: int = 0,
    active_containers: set[int] | None = None,
) -> Any:
    if depth > MAX_NESTING_DEPTH:
        raise CanonicalizationError(
            f"value nesting at {path} exceeds the {MAX_NESTING_DEPTH}-level limit"
        )

    if value is None or isinstance(value, bool):
        return value

    if isinstance(value, str):
        _validate_string(value, path)
        return value

    if isinstance(value, int):
        if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalizationError(
                f"integer at {path} is outside the interoperable JSON range "
                f"[{MIN_SAFE_INTEGER}, {MAX_SAFE_INTEGER}]"
            )
        return value

    if isinstance(value, float):
        raise CanonicalizationError(
            f"floating-point value at {path} is not supported by {CANONICAL_FORMAT}; "
            "encode exact decimal values as strings or schema-defined integers"
        )

    if isinstance(value, (list, dict)):
        if active_containers is None:
            active_containers = set()
        identity = id(value)
        if identity in active_containers:
            raise CanonicalizationError(f"cyclic container reference at {path}")
        active_containers.add(identity)
        try:
            if isinstance(value, list):
                return [
                    _prepare(item, f"{path}[{index}]", depth + 1, active_containers)
                    for index, item in enumerate(value)
                ]

            for key in value:
                if not isinstance(key, str):
                    raise CanonicalizationError(
                        f"object key at {path} must be a string, got {type(key).__name__}"
                    )
                _validate_string(key, f"{path}.<key>")

            return {
                key: _prepare(value[key], f"{path}.{key}", depth + 1, active_containers)
                for key in sorted(value, key=_utf16_sort_key)
            }
        finally:
            active_containers.remove(identity)

    raise CanonicalizationError(f"unsupported value at {path}: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON value to the platform's canonical UTF-8 representation.

    v1 rules:
    - object keys are sorted by UTF-16 code units;
    - no insignificant whitespace is emitted;
    - Unicode is encoded directly as UTF-8 rather than ASCII escapes;
    - only null, strings, booleans, interoperable integers, arrays, and objects
      with string keys are accepted;
    - cyclic containers, excessive nesting, floating point, and non-JSON values
      fail closed.
    """

    prepared = _prepare(value)
    serialized = json.dumps(
        prepared,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return serialized.encode("utf-8")


def content_digest(value: Any) -> str:
    """Return a format-bound SHA-256 digest of canonical content."""

    digest = hashlib.sha256(_DIGEST_DOMAIN + canonical_json_bytes(value)).hexdigest()
    return f"{DIGEST_ALGORITHM}:{CANONICAL_FORMAT}:{digest}"
