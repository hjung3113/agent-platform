"""Subprocess entrypoint for the M6 stub Verifier."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from kernel.canonical import canonical_json_bytes, content_digest
from kernel.protocol import ProtocolRejected, RecordRef, read_record_ref
from kernel.protocol_v1 import TaskV1, VerificationV1

from execution.opencode_adapter import probe_opencode_profile
from verification.stub_verifier import stub_verify


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name}_not_object")
    return value


def _require_nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name}_not_nonempty_string")
    return value


def _read_task(value: Any) -> TaskV1:
    candidate = _require_object(value, "task")
    required = {"task_id", "objective", "acceptance_criteria"}
    if set(candidate) != required:
        raise ValueError("task_keys_mismatch")
    criteria = candidate["acceptance_criteria"]
    if not isinstance(criteria, list):
        raise ValueError("task_acceptance_criteria_not_list")
    return TaskV1(
        task_id=_require_nonempty_string(candidate["task_id"], "task_id"),
        objective=_require_nonempty_string(candidate["objective"], "task_objective"),
        acceptance_criteria=tuple(
            _require_nonempty_string(item, "task_acceptance_criterion")
            for item in criteria
        ),
    )


def _read_result_ref(value: Any) -> RecordRef:
    try:
        result_ref = read_record_ref(value)
    except ProtocolRejected as rejection:
        raise ValueError(
            f"result_ref_rejected:{rejection.code}:{rejection.reason}"
        ) from rejection
    if result_ref.contract_kind != "result":
        raise ValueError("result_ref_kind_not_result")
    return result_ref


def _build_verification(payload: Any) -> VerificationV1:
    candidate = _require_object(payload, "verifier_input")
    required = {
        "result_ref",
        "result_output_snapshot_digest",
        "task",
        "verifier_identity",
        "expected_output_digest",
        "opencode_binary_path",
        "config_paths",
    }
    if set(candidate) != required:
        raise ValueError("verifier_input_keys_mismatch")

    config_paths = candidate["config_paths"]
    if not isinstance(config_paths, list):
        raise ValueError("config_paths_not_list")
    if any(not isinstance(path, str) or not path for path in config_paths):
        raise ValueError("config_path_not_nonempty_string")

    result_ref = _read_result_ref(candidate["result_ref"])
    task = _read_task(candidate["task"])
    verifier_identity = _require_nonempty_string(
        candidate["verifier_identity"], "verifier_identity"
    )
    result_output_snapshot_digest = _require_nonempty_string(
        candidate["result_output_snapshot_digest"],
        "result_output_snapshot_digest",
    )
    expected_output_digest = _require_nonempty_string(
        candidate["expected_output_digest"], "expected_output_digest"
    )
    binary_path = _require_nonempty_string(
        candidate["opencode_binary_path"], "opencode_binary_path"
    )
    profile = probe_opencode_profile(
        binary_path, tuple(Path(path) for path in config_paths)
    )
    verifier_execution_identity = content_digest(
        {
            "started_at_ns": str(time.time_ns()),
            "nonce": os.urandom(16).hex(),
        }
    )
    return stub_verify(
        result_ref=result_ref,
        result_output_snapshot_digest=result_output_snapshot_digest,
        task=task,
        verifier_identity=verifier_identity,
        verifier_runtime_capability_profile_identity=profile.identity,
        verifier_execution_identity=verifier_execution_identity,
        expected_output_digest=expected_output_digest,
    )


def main() -> int:
    try:
        verification = _build_verification(json.loads(sys.stdin.read()))
        sys.stdout.write(
            canonical_json_bytes(verification.to_canonical_value()).decode("utf-8")
        )
        sys.stdout.write("\n")
    except (OSError, TypeError, ValueError, json.JSONDecodeError, ProtocolRejected) as error:
        print(
            f"stub_verifier_cli_failure:{type(error).__name__}:{error}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
