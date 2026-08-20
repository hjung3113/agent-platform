#!/usr/bin/env python3
"""Deterministic fake ``opencode`` binary for adapter conformance tests.

M3 plan §9: runtime-capability adapter tests point ``binary_path`` at this
fixture so the suite needs no real OpenCode install and no network access.
"""

import sys

VERSION = "fake-opencode 1.2.3"


def main() -> int:
    if sys.argv[1:] == ["--version"]:
        print(VERSION)
        return 0
    print(f"fake-opencode: unsupported arguments: {sys.argv[1:]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
