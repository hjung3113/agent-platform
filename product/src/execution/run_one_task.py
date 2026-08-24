"""Minimal M3 reference driver for one published task chain."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.protocol import ContractKind, ParsedCandidate, RecordRef, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    AttemptPacketV1,
    ReceiptV1,
    RequestV1,
    ResultV1,
    TaskV1,
    VerificationV1,
    WorkflowRevisionV1,
    schema_version_for_kind,
)
from kernel.publish import Published, Rejected, publish

from execution import host
from execution.attempt import build_attempt_packet, build_receipt
from execution.context_compiler import compile_context_pack, disclosure_identity
from execution.context_evidence import write_context_evidence

_VERIFIER_DIAGNOSTIC_LIMIT = 4096


class VerifierSubprocessError(Exception):
    """The verifier child failed or did not emit a valid Verification."""


@dataclass(frozen=True)
class RunOneTaskResult:
    """Published identities and typed values for one complete task chain."""

    run_id: str
    request: Published
    request_value: RequestV1
    workflow: Published
    workflow_value: WorkflowRevisionV1
    attempt: Published
    attempt_value: AttemptPacketV1
    result: Published
    result_value: ResultV1
    verification: Published
    verification_value: VerificationV1
    receipt: Published | None
    receipt_value: ReceiptV1 | None

    @property
    def workflow_revision(self) -> Published:
        """Alias matching the protocol record name."""

        return self.workflow

    @property
    def workflow_revision_value(self) -> WorkflowRevisionV1:
        """Alias matching the protocol value name."""

        return self.workflow_value

    @property
    def attempt_packet(self) -> Published:
        """Alias matching the protocol record name."""

        return self.attempt

    @property
    def attempt_packet_value(self) -> AttemptPacketV1:
        """Alias matching the protocol value name."""

        return self.attempt_value


def _as_candidate(contract_kind: str, typed: Any) -> ParsedCandidate:
    """Read a typed value through the public candidate reader dispatch."""

    read = read_candidate(
        {
            "contract_kind": contract_kind,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind(contract_kind)),
            "payload": typed.to_canonical_value(),
        }
    )
    if not read.ok:
        raise RuntimeError(
            f"candidate rejected for {contract_kind}: "
            f"{read.rejection_code}:{read.reason}"
        )
    return read.value


def _require_published(step: str, result: Published | Rejected) -> Published:
    """Fail loudly if the expected golden-path publication was rejected."""

    if isinstance(result, Rejected):
        raise RuntimeError(
            f"unexpected publish rejection at step {step}: {result.code}"
        )
    return result


def _truncate_verifier_diagnostic(value: object) -> str:
    rendered = "<none>" if value is None else str(value)
    if len(rendered) <= _VERIFIER_DIAGNOSTIC_LIMIT:
        return rendered
    return rendered[:_VERIFIER_DIAGNOSTIC_LIMIT] + "...<truncated>"


def _verifier_subprocess_error(
    reason: str,
    *,
    command: object,
    stdout: object,
    stderr: object,
) -> VerifierSubprocessError:
    return VerifierSubprocessError(
        f"{reason}; cmd={command!r}; "
        f"stdout={_truncate_verifier_diagnostic(stdout)!r}; "
        f"stderr={_truncate_verifier_diagnostic(stderr)!r}"
    )


def _run_verifier_subprocess(
    *,
    result_ref: RecordRef,
    result_output_snapshot_digest: str,
    task: TaskV1,
    verifier_identity: str,
    expected_output_digest: str,
    opencode_binary_path: str,
    config_paths: tuple[Path, ...],
) -> VerificationV1:
    input_payload = {
        "result_ref": result_ref.to_canonical_value(),
        "result_output_snapshot_digest": result_output_snapshot_digest,
        "task": task.to_canonical_value(),
        "verifier_identity": verifier_identity,
        "expected_output_digest": expected_output_digest,
        "opencode_binary_path": opencode_binary_path,
        "config_paths": [str(path) for path in config_paths],
    }
    command = [sys.executable, "-m", "verification.stub_verifier_cli"]
    child_environment = os.environ.copy()
    src_root = str(Path(__file__).resolve().parents[1])
    existing_pythonpath = child_environment.get("PYTHONPATH")
    child_environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (src_root, existing_pythonpath) if path
    )
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(input_payload),
            capture_output=True,
            check=True,
            text=True,
            env=child_environment,
        )
    except subprocess.CalledProcessError as error:
        raise _verifier_subprocess_error(
            f"verifier_subprocess_failed_returncode={error.returncode}",
            command=error.cmd,
            stdout=error.stdout,
            stderr=error.stderr,
        ) from error
    except OSError as error:
        raise _verifier_subprocess_error(
            f"verifier_subprocess_spawn_failed={error}",
            command=command,
            stdout=None,
            stderr=str(error),
        ) from error

    try:
        payload = json.loads(completed.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise _verifier_subprocess_error(
            "verifier_stdout_malformed",
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
        ) from error
    parsed = read_candidate(
        {
            "contract_kind": ContractKind.VERIFICATION.value,
            "protocol_version": PROTOCOL_VERSION,
            "schema_version": schema_version_for_kind(ContractKind.VERIFICATION),
            "payload": payload,
        }
    )
    if not parsed.ok:
        raise _verifier_subprocess_error(
            f"verifier_stdout_rejected={parsed.rejection_code}:{parsed.reason}",
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    if not isinstance(parsed.value.value, VerificationV1):
        raise _verifier_subprocess_error(
            "verifier_stdout_not_verification",
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
    return parsed.value.value


def run_one_task(
    state: str,
    request: RequestV1,
    task: TaskV1,
    workspace_root: Path,
    opencode_binary_path: str,
    *,
    implementer_identity: str,
    verifier_identity: str,
    expected_output_digest: str,
    config_paths: tuple[Path, ...] = (),
    declared_generated_paths: tuple[str, ...] = (),
    contract_refs: tuple[RecordRef, ...] = (),
    idempotency_prefix: str = "run",
) -> RunOneTaskResult:
    """Run and publish the M3 Request-to-Receipt one-task chain."""

    request_published = _require_published(
        "request",
        publish(
            state,
            None,
            _as_candidate("request", request),
            None,
            f"{idempotency_prefix}-request",
        ),
    )

    workflow_value = WorkflowRevisionV1(
        request=request_published.record_ref,
        task=task,
    )
    workflow_published = _require_published(
        "workflow_revision",
        publish(
            state,
            request_published.run_id,
            _as_candidate("workflow_revision", workflow_value),
            request_published.record_ref,
            f"{idempotency_prefix}-workflow",
        ),
    )

    attempt_value = build_attempt_packet(
        workflow_revision_ref=workflow_published.record_ref,
        task_id=task.task_id,
        implementer_identity=implementer_identity,
        state=state,
        run_id=request_published.run_id,
        task=task,
        workspace_root=workspace_root,
        opencode_binary_path=opencode_binary_path,
        config_paths=config_paths,
        declared_generated_paths=declared_generated_paths,
        contract_refs=contract_refs,
    )
    attempt_published = _require_published(
        "attempt_packet",
        publish(
            state,
            request_published.run_id,
            _as_candidate("attempt_packet", attempt_value),
            workflow_published.record_ref,
            f"{idempotency_prefix}-attempt",
        ),
    )

    # Evidence-only recompile with identical inputs (pure, side-effect-free);
    # by construction it must reproduce the packet's compiled context digest.
    evidence_pack = compile_context_pack(
        task_id=task.task_id,
        task_objective=task.objective,
        task_acceptance_criteria=task.acceptance_criteria,
        workspace_snapshot_digest=attempt_value.workspace_snapshot_digest,
        runtime_capability_profile_identity=(
            attempt_value.runtime_capability_profile_identity
        ),
        contract_refs=contract_refs,
        disclosure_identity=disclosure_identity(
            attempt_value.runtime_capability_profile_identity, "v1"
        ),
    )
    if evidence_pack.digest != attempt_value.context_digest:
        # Real invariant violation, not a debug-only guard (PR #47 review
        # round 2 LOW 3 — a bare `assert` here vanishes under `python -O`,
        # letting a divergent evidence file be written unverified).
        raise RuntimeError(
            "evidence-only recompile diverged from the published Attempt "
            "Packet's context_digest: "
            f"evidence={evidence_pack.digest} attempt={attempt_value.context_digest}"
        )
    # Evidence is inspectable record-keeping only (execution/context_evidence.py's
    # own docstring): nothing depends on this file existing, so a storage
    # failure here must never abort an already-admitted, otherwise-successful
    # run (PR #47 review P1 — evidence write had become a silent hard
    # dependency of execution by being un-guarded ahead of host.execute()).
    try:
        write_context_evidence(
            state, attempt_published.record_ref.record_id, evidence_pack
        )
    except OSError:
        pass

    result_value = host.execute(
        attempt_published.record_ref,
        attempt_value,
        workspace_root,
        opencode_binary_path,
        task,
        state,
        request_published.run_id,
        config_paths,
        declared_generated_paths,
        contract_refs=contract_refs,
    )
    result_published = _require_published(
        "result",
        publish(
            state,
            request_published.run_id,
            _as_candidate("result", result_value),
            attempt_published.record_ref,
            f"{idempotency_prefix}-result",
        ),
    )

    verification_value = _run_verifier_subprocess(
        result_ref=result_published.record_ref,
        result_output_snapshot_digest=result_value.output_snapshot_digest,
        task=task,
        verifier_identity=verifier_identity,
        expected_output_digest=expected_output_digest,
        opencode_binary_path=opencode_binary_path,
        config_paths=config_paths,
    )
    verification_published = _require_published(
        "verification",
        publish(
            state,
            request_published.run_id,
            _as_candidate("verification", verification_value),
            result_published.record_ref,
            f"{idempotency_prefix}-verification",
        ),
    )

    receipt_value: ReceiptV1 | None = None
    receipt_published: Published | None = None
    if verification_value.verdict == "PASS":
        receipt_value = build_receipt(
            verification_ref=verification_published.record_ref
        )
        receipt_published = _require_published(
            "receipt",
            publish(
                state,
                request_published.run_id,
                _as_candidate("receipt", receipt_value),
                verification_published.record_ref,
                f"{idempotency_prefix}-receipt",
            ),
        )

    return RunOneTaskResult(
        run_id=request_published.run_id,
        request=request_published,
        request_value=request,
        workflow=workflow_published,
        workflow_value=workflow_value,
        attempt=attempt_published,
        attempt_value=attempt_value,
        result=result_published,
        result_value=result_value,
        verification=verification_published,
        verification_value=verification_value,
        receipt=receipt_published,
        receipt_value=receipt_value,
    )
