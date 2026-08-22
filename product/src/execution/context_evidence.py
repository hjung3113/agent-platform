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
from pathlib import Path

from execution.context_compiler import ContextPack


def write_context_evidence(state: str, attempt_record_id: str, pack: ContextPack) -> Path:
    """Atomically write one Attempt's full Context Pack as JSON evidence.

    Mirrors ``kernel.lineage_store``'s temp-file + rename idiom so a crash
    mid-write never leaves a partial evidence file. Returns the final path.
    """

    evidence_dir = Path(state) / "context-evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    final_path = evidence_dir / f"{attempt_record_id}.json"
    temp_path = evidence_dir / f".{attempt_record_id}.json.tmp"
    payload = json.dumps(pack.to_canonical_value(), indent=2, ensure_ascii=False)
    with open(temp_path, "w", encoding="utf-8") as temp_file:
        temp_file.write(payload)
        temp_file.flush()
        os.fsync(temp_file.fileno())
    try:
        os.replace(temp_path, final_path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return final_path
