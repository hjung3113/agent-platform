"""Filesystem lineage primitive for authoritative run records.

This module is a dumb, crash-safe storage primitive only: it knows nothing
about contract kinds, protocol semantics, or authority. Sequence assignment
and publication semantics belong to callers holding the run lock.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

_SEQUENCE_FILENAME = re.compile(r"^(\d{10})\.json$")
_HEAD_FILENAME = "_head.json"
_LOCK_FILENAME = "_lock"


class SequenceConflictError(Exception):
    """Raised when appending a sequence number that already exists on disk."""


@dataclass(frozen=True)
class HeadProjection:
    """Derived, rebuildable projection of a run's committed lineage."""

    last_sequence: int
    last_record_file: str
    last_record: dict


def open_run(state_dir: str, run_id: str) -> RunHandle:
    """Open (creating if needed) the run directory under ``state_dir``.

    Run-id uniqueness is the caller's responsibility; this only ensures the
    ``runs/{run_id}`` directory exists.
    """

    run_dir = Path(state_dir) / "runs" / run_id
    os.makedirs(run_dir, exist_ok=True)
    return RunHandle(run_dir)


@dataclass(frozen=True)
class RunHandle:
    """Handle to one run's on-disk lineage directory."""

    run_dir: Path

    def _sequence_path(self, seq: int) -> Path:
        return self.run_dir / f"{seq:010d}.json"

    def append(self, seq: int, record_bytes: bytes) -> None:
        """Atomically commit one record at ``seq`` via temp-file + rename.

        Raises ``SequenceConflictError`` if the target file already exists;
        an existing committed record is never overwritten.
        """

        final_path = self._sequence_path(seq)
        if final_path.exists():
            raise SequenceConflictError(f"sequence already committed: {seq}")
        temp_path = self.run_dir / f".{seq:010d}.json.tmp"
        with open(temp_path, "wb") as temp_file:
            temp_file.write(record_bytes)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        try:
            if final_path.exists():
                raise SequenceConflictError(f"sequence already committed: {seq}")
            os.rename(temp_path, final_path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise

    def _head_path(self) -> Path:
        return self.run_dir / _HEAD_FILENAME

    def read_head(self) -> HeadProjection | None:
        """Return the persisted head projection, or None if missing/corrupt."""

        try:
            raw = self._head_path().read_bytes()
        except (FileNotFoundError, NotADirectoryError):
            return None
        try:
            value = json.loads(raw.decode("utf-8"))
            return HeadProjection(
                last_sequence=value["last_sequence"],
                last_record_file=value["last_record_file"],
                last_record=value["last_record"],
            )
        except (ValueError, KeyError, TypeError):
            return None

    def write_head(self, head: HeadProjection) -> None:
        """Atomically persist the head projection via temp-file + rename."""

        payload = {
            "last_sequence": head.last_sequence,
            "last_record_file": head.last_record_file,
            "last_record": head.last_record,
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode(
            "utf-8"
        )
        temp_path = self.run_dir / ".head.json.tmp"
        with open(temp_path, "wb") as temp_file:
            temp_file.write(encoded)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.rename(temp_path, self._head_path())

    def rebuild_head_from_scan(self) -> HeadProjection:
        """Rebuild the head projection by scanning committed sequence files."""

        sequences: list[tuple[int, str]] = []
        for entry in os.listdir(self.run_dir):
            match = _SEQUENCE_FILENAME.fullmatch(entry)
            if match is not None:
                sequences.append((int(match.group(1)), entry))
        if not sequences:
            raise ValueError(f"no committed records in run dir: {self.run_dir}")
        sequences.sort()
        last_sequence, last_record_file = sequences[-1]
        last_record = json.loads(
            (self.run_dir / last_record_file).read_bytes().decode("utf-8")
        )
        return HeadProjection(
            last_sequence=last_sequence,
            last_record_file=last_record_file,
            last_record=last_record,
        )

    @contextmanager
    def lock(self) -> Iterator[None]:
        """Hold the run's exclusive advisory lock for a critical section."""

        lock_path = self.run_dir / _LOCK_FILENAME
        lock_file = open(lock_path, "a+b")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()
