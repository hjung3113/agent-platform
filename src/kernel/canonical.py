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


class CanonicalizationError(ValueError):
    """Raised when a value cannot be represented by the canonical format."""


def _validate_string(value: str, path: str) -> None:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CanonicalizationError(f"invalid Unicode string at {path}") from exc


def _validate(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, bool):
        return

    if isinstance(value, str):
        _validate_string(value, path)
        return

    if isinstance(value, int):
        if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise CanonicalizationError(
                f"integer at {path} is outside the interoperable JSON range "
                f"[{MIN_SAFE_INTEGER}, {MAX_SAFE_INTEGER}]"
            )
        return

    if isinstance(value, float):
        raise CanonicalizationError(
            f"floating-point value at {path} is not supported by {CANONICAL_FORMAT}; "
            "encode exact decimal values as strings or schema-defined integers"
        )

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate(item, f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(
                    f"object key at {path} must be a string, got {type(key).__name__}"
                )
            _validate_string(key, f"{path}.<key>")
            _validate(item, f"{path}.{key}")
        return

    raise CanonicalizationError(f"unsupported value at {path}: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a JSON value to the platform's canonical UTF-8 representation.

    v1 rules:
    - object keys are sorted lexicographically;
    - no insignificant whitespace is emitted;
    - Unicode is encoded directly as UTF-8 rather than ASCII escapes;
    - only null, strings, booleans, interoperable integers, arrays, and objects
      with string keys are accepted;
    - floating point and non-JSON values fail closed.
    """

    _validate(value)
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return serialized.encode("utf-8")


def content_digest(value: Any) -> str:
    """Return the stable SHA-256 digest of canonical content."""

    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"{DIGEST_ALGORITHM}:{digest}"
