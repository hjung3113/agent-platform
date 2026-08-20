"""Minimal M3 reference driver for one published task chain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kernel.protocol import ParsedCandidate, read_candidate
from kernel.protocol_v1 import (
    PROTOCOL_VERSION,
    SCHEMA_VERSION,
    AttemptPacketV1,
    ReceiptV1,
    RequestV1,
    ResultV1,
    TaskV1,
    VerificationV1,
    WorkflowRevisionV1,
)
from kernel.publish import Published, Rejected, publish

from execution import host
from execution.attempt import build_attempt_packet, build_receipt
from verification.stub_verifier import stub_verify


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
            "schema_version": SCHEMA_VERSION,
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
        workspace_root=workspace_root,
        opencode_binary_path=opencode_binary_path,
        config_paths=config_paths,
        declared_generated_paths=declared_generated_paths,
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

    result_value = host.execute(
        attempt_published.record_ref,
        attempt_value,
        workspace_root,
        opencode_binary_path,
        config_paths,
        declared_generated_paths,
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

    verification_value = stub_verify(
        result_ref=result_published.record_ref,
        result_output_snapshot_digest=result_value.output_snapshot_digest,
        task=task,
        verifier_identity=verifier_identity,
        expected_output_digest=expected_output_digest,
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
