"""Deterministic canary scanning before captured output is retained.

Callers that have captured bytes must decode them with strict UTF-8 before calling
``scan_for_retention``.  They pass ``None`` when decoding failed or when the
content cannot be determined.  The scanner never returns or logs matched text;
it reports only fixed pattern-class names.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class RedactionStatus(str, Enum):
    PASSED = "passed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RedactionResult:
    status: str
    reasons: tuple[str, ...] = ()


_AWS_ACCESS_KEY_PATTERN = re.compile(r"AKIA[0-9A-Z]{16}")
_PEM_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN[ A-Z]*PRIVATE KEY-----.*?-----END[ A-Z]*PRIVATE KEY-----",
    re.DOTALL,
)
_HIGH_ENTROPY_TOKEN_PATTERN = re.compile(
    r'''(?i)(?:bearer|token|secret|key|api[_-]?key|password)\s*[:=]\s*['"]?[A-Za-z0-9_-]{20,}['"]?'''
)

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_AWS_ACCESS_KEY_PATTERN, "aws_access_key"),
    (_PEM_PRIVATE_KEY_PATTERN, "pem_private_key"),
    (_HIGH_ENTROPY_TOKEN_PATTERN, "high_entropy_token"),
)


def _unknown_result() -> RedactionResult:
    return RedactionResult(RedactionStatus.UNKNOWN.value)


def scan_for_retention(text: str | None) -> RedactionResult:
    """Return whether text is safe to retain under the M3 canary gate.

    ``None`` is the sentinel for content that could not be decoded as UTF-8 or
    otherwise could not be inspected.  Non-string values are also treated as
    unknown defensively; byte decoding remains the caller's responsibility.
    """

    if text is None or not isinstance(text, str):
        return _unknown_result()

    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return _unknown_result()

    reasons = {
        reason for pattern, reason in _PATTERNS if pattern.search(text) is not None
    }
    if reasons:
        return RedactionResult(
            RedactionStatus.BLOCKED.value,
            tuple(sorted(reasons)),
        )
    return RedactionResult(RedactionStatus.PASSED.value)
