"""M2 stub Host: deterministic fake execution of a published Attempt Packet.

No process, subprocess, network, or filesystem execution happens here — the
output snapshot digest is a pure function of the published Attempt Packet's
content digest. This is the explicit fake Host identity the M2 gate requires;
real Host isolation is M3.
"""

from __future__ import annotations

from kernel.canonical import content_digest
from kernel.protocol import RecordRef
from kernel.protocol_v1 import ResultV1, RuntimeObservationV1

_FIXTURE_TAG = "m2-stub-host"
_RUNTIME_IDENTITY = "m2-stub-host-runtime-v1"


def stub_execute(attempt_ref: RecordRef) -> ResultV1:
    """Deterministically derive a Result candidate from a published Attempt Packet.

    ``kernel.admission.admit_attempt`` is not called: its signature requires a
    real ``workspace_root`` path and ``RuntimeCapabilityProfile`` that a pure
    stub does not have, and fabricating them would prove nothing.
    """

    output_snapshot_digest = content_digest(
        {"fixture": _FIXTURE_TAG, "attempt_content_digest": attempt_ref.content_digest}
    )
    return ResultV1(
        attempt=attempt_ref,
        output_snapshot_digest=output_snapshot_digest,
        observation=RuntimeObservationV1(
            runtime_identity=_RUNTIME_IDENTITY,
            output_snapshot_digest=output_snapshot_digest,
        ),
    )
