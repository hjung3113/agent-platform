"""Pure replay reducer over a run's committed lineage records.

``replay()`` independently re-reads the committed ``NNNNNNNNNN.json`` record
envelopes under ``{state_dir}/runs/{run_id}/`` — never the derived
``_head.json`` projection — and re-parses each record's ``candidate`` through
the real ``kernel.protocol.read_candidate`` dispatch, so the folded values are
the same typed values a live ``publish()`` would have validated.

The reducer proves the run's authority is recoverable from the committed
record files alone: a missing, stale, or corrupt head projection cannot
change what replay returns.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from kernel.canonical import content_digest
from kernel.protocol import RecordRef, read_candidate
from kernel.protocol_v1 import RequestV1, WorkflowRevisionV1

_RECORD_FILENAME = re.compile(r"^(\d{10})\.json$")


@dataclass(frozen=True)
class RunState:
    """Reduced state of one run's committed lineage."""

    request: RequestV1 | None
    workflow_revision: WorkflowRevisionV1 | None
    last_sequence: int
    last_record_id: RecordRef | None


def _committed_envelopes(run_dir: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield ``(sequence, envelope)`` for committed records, in sequence order.

    Mirrors the run-directory layout ``kernel.lineage_store`` writes: one
    JSON envelope per ``{sequence:010d}.json`` file. Reading is done through
    plain file listing on purpose — replay must not import publish-private
    helpers nor create the run directory the way ``open_run`` does.
    """

    sequences: list[tuple[int, str]] = []
    for entry in os.listdir(run_dir):
        match = _RECORD_FILENAME.fullmatch(entry)
        if match is not None:
            sequences.append((int(match.group(1)), entry))
    sequences.sort()
    for sequence, name in sequences:
        envelope = json.loads((run_dir / name).read_bytes().decode("utf-8"))
        if not isinstance(envelope, dict):
            raise ValueError(f"committed record {name} is not a JSON object")
        yield sequence, envelope


def replay(state_dir: str, run_id: str) -> RunState:
    """Fold a run's committed records into ``RunState``, ignoring ``_head.json``.

    A missing run directory or a run with no committed records is a valid
    "no publications yet" state and returns the empty ``RunState`` rather
    than raising; the run directory is never created as a side effect.

    A committed record whose envelope metadata does not verify — a content
    digest that does not match the recomputed digest of its ``candidate``,
    a ``record_id``/``run_id``/``sequence`` that disagrees with the
    deterministic publication scheme, or a gap in the committed sequence —
    is an integrity fault and fails closed with ``ValueError``.

    A committed record whose candidate no longer parses through the current
    protocol dispatch is an integrity fault, not a "no publications yet"
    state, and fails closed with ``ValueError``.

    The fold is deterministic and side-effect-free: repeated calls without
    intervening ``publish()`` calls return equal ``RunState`` values. M1
    publishes at most one genesis ``RequestV1`` (the last one seen wins) and
    ``workflow_revision`` holds the highest-sequence ``WorkflowRevisionV1``.
    """

    run_dir = Path(state_dir) / "runs" / run_id
    request: RequestV1 | None = None
    workflow_revision: WorkflowRevisionV1 | None = None
    last_sequence = 0
    last_record_id: RecordRef | None = None

    if not run_dir.is_dir():
        return RunState(
            request=request,
            workflow_revision=workflow_revision,
            last_sequence=last_sequence,
            last_record_id=last_record_id,
        )

    expected_sequence = 0
    for sequence, envelope in _committed_envelopes(run_dir):
        expected_sequence += 1
        if sequence != expected_sequence:
            raise ValueError(
                f"committed record sequence gap in run {run_id}: expected"
                f" {expected_sequence:010d}, found {sequence:010d}"
            )
        candidate = envelope.get("candidate")
        if envelope.get("content_digest") != content_digest(candidate):
            raise ValueError(
                f"committed record {run_id}/{sequence:010d} content digest"
                " mismatch"
            )
        if envelope.get("record_id") != f"{run_id}:{sequence:010d}":
            raise ValueError(
                f"committed record {run_id}/{sequence:010d} record_id mismatch"
            )
        if envelope.get("run_id") != run_id:
            raise ValueError(
                f"committed record {run_id}/{sequence:010d} run_id mismatch"
            )
        if envelope.get("sequence") != sequence:
            raise ValueError(
                f"committed record {run_id}/{sequence:010d} sequence mismatch"
            )
        result = read_candidate(candidate)
        if not result.ok:
            raise ValueError(
                f"committed record {run_id}/{sequence:010d} failed protocol"
                f" dispatch: {result.rejection_code}:{result.reason}"
            )
        value = result.value.value
        if isinstance(value, RequestV1):
            request = value
        elif isinstance(value, WorkflowRevisionV1):
            workflow_revision = value
        candidate = envelope["candidate"]
        last_sequence = sequence
        last_record_id = RecordRef(
            contract_kind=candidate["contract_kind"],
            record_id=envelope["record_id"],
            content_digest=envelope["content_digest"],
        )

    return RunState(
        request=request,
        workflow_revision=workflow_revision,
        last_sequence=last_sequence,
        last_record_id=last_record_id,
    )
