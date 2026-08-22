"""Inspectable evidence files for compiled Context Packs.

One JSON file per Attempt, at ``{state_dir}/context-evidence/{record_id}.json``
— a sibling of the Kernel lineage store's ``runs/`` tree, structurally
outside it (that tree's one-writer boundary belongs to ``kernel.publish``
alone) and outside any managed Git workspace. This is record-keeping only:
nothing depends on the file existing for an Attempt to be admitted or
executed.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from execution.context_compiler import ContextPack


def write_context_evidence(state: str, attempt_record_id: str, pack: ContextPack) -> Path:
    """Atomically write one Attempt's full Context Pack as JSON evidence.

    Mirrors ``kernel.lineage_store``'s temp-file + rename idiom so a crash
    mid-write never leaves a partial evidence file. The temp file gets a
    unique name per call (``tempfile.mkstemp``, same directory as the
    final path) rather than a fixed ``{record_id}.json.tmp`` name, so two
    concurrent writers for the same ``attempt_record_id`` (e.g. two
    idempotent-retry callers) never race on the same temp path and cause
    one writer's ``os.replace`` to lose its source file out from under it.
    Returns the final path.
    """

    evidence_dir = Path(state) / "context-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    final_path = evidence_dir / f"{attempt_record_id}.json"
    payload = json.dumps(pack.to_canonical_value(), indent=2, ensure_ascii=False)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{attempt_record_id}.", suffix=".tmp", dir=evidence_dir
    )
    temp_path = Path(temp_name)
    try:
        # mkstemp always creates its file mode 0600 (ignoring umask, by
        # design) — chmod to the same 0644 lineage_store.append's plain
        # open(..., "wb") produces under the common default umask, so
        # evidence files land at the same permissions as the authoritative
        # records they describe rather than being unreadable to any other
        # account on the host (PR #47 review round 2 LOW 4).
        os.chmod(temp_path, 0o644)
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, final_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return final_path
