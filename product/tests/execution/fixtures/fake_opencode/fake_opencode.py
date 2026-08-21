#!/usr/bin/env python3
"""Deterministic fake ``opencode`` binary for adapter and Host conformance tests.

M3 plan §9: tests point ``binary_path`` at this fixture so the suite needs no
real OpenCode install and no network access.

Modes:

* ``--version`` — print ``VERSION`` and exit 0 (adapter probe path).
* ``run <message> --workdir <dir>`` — the Host's process-spawn path (plan §6
  step 4). ``<message>`` mirrors real OpenCode's ``run [message..]`` positional
  task text (PR review: the Host must actually pass the admitted task's
  description to the runtime, not spawn it blind). Reads its actual cwd,
  environment, and received message, and writes exactly one deterministic
  report file, ``fake-opencode-report.json``, into the workdir recording the
  resolved ``cwd``, the ``--workdir`` argument, the received ``message``, the
  sorted visible environment variable *names* (values are never recorded),
  and whether the test sentinel variable was visible — used to prove the
  child environment is allow-listed, not inherited. If the workdir contains a
  ``fake-opencode-directive.txt``, its content selects a canned outcome
  instead of the normal report:
  - ``noop`` — nothing is written, only a success line prints — used to prove
    Result completion is derived from workspace snapshot identity, not from
    stdout or exit code.
  - ``stdout-canary`` — prints a synthetic AWS-key-shaped canary to stdout.
  - ``fail`` — prints a failure line to stderr and exits 3 — used to prove a
    genuinely failed run does not silently produce a successful Result.
  - ``invalid-utf8-stdout`` — writes non-UTF8 bytes to stdout and exits 0 —
    used to prove the Host's redaction scan degrades to "unknown" rather than
    crashing on undecodable captured output.
  Any other directive content exits 2 rather than improvising behavior.
"""

import json
import os
import sys
from pathlib import Path

VERSION = "fake-opencode 1.2.3"
REPORT_NAME = "fake-opencode-report.json"
DIRECTIVE_NAME = "fake-opencode-directive.txt"
SENTINEL_VARIABLE = "SENTINEL_SECRET"
REDACTION_CANARY = "AKIAABCDEFGHIJKLMNOP"


def _version() -> int:
    print(VERSION)
    return 0


def _run(arguments: list[str]) -> int:
    workdir_argument = ""
    if "--workdir" in arguments:
        index = arguments.index("--workdir")
        if index + 1 >= len(arguments):
            print("fake-opencode: --workdir requires a value", file=sys.stderr)
            return 2
        workdir_argument = arguments[index + 1]
        message_arguments = arguments[:index] + arguments[index + 2 :]
    else:
        message_arguments = list(arguments)
    message = message_arguments[0] if message_arguments else ""
    workdir = Path(workdir_argument) if workdir_argument else Path.cwd()

    directive = workdir / DIRECTIVE_NAME
    if directive.is_file():
        content = directive.read_text(encoding="utf-8").strip()
        if content == "noop":
            print("opencode: success (no-op)")
            return 0
        if content == "stdout-canary":
            print(f"opencode: synthetic canary {REDACTION_CANARY}")
            return 0
        if content == "fail":
            print("opencode: run failed", file=sys.stderr)
            return 3
        if content == "invalid-utf8-stdout":
            sys.stdout.buffer.write(b"opencode: \xff\xfe not valid utf-8\n")
            sys.stdout.buffer.flush()
            return 0
        print(f"fake-opencode: unknown directive: {content!r}", file=sys.stderr)
        return 2

    report = {
        "argv": list(sys.argv),
        "cwd": os.getcwd(),
        "workdir_argument": workdir_argument,
        "message": message,
        "env_keys": sorted(os.environ),
        "sentinel_secret_seen": SENTINEL_VARIABLE in os.environ,
    }
    (workdir / REPORT_NAME).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("opencode: run complete")
    return 0


def main() -> int:
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        return _version()
    if arguments[:1] == ["run"]:
        return _run(arguments[1:])
    print(f"fake-opencode: unsupported arguments: {arguments}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
