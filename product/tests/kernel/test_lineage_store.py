from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from kernel.lineage_store import (
    HeadProjection,
    SequenceConflictError,
    open_run,
)


def record_bytes(seq: int, marker: str = "record") -> bytes:
    return json.dumps({"seq": seq, "marker": marker}).encode("utf-8")


class LineageStoreTests(unittest.TestCase):
    def test_append_is_atomic_no_partial_final_file_on_rename_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = open_run(directory, "run-1")
            with mock.patch("os.rename", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    run.append(1, record_bytes(1))
            self.assertFalse((run.run_dir / "0000000001.json").exists())

    def test_duplicate_sequence_is_rejected_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = open_run(directory, "run-1")
            run.append(1, record_bytes(1, "first"))
            with self.assertRaises(SequenceConflictError):
                run.append(1, record_bytes(1, "second"))
            content = (run.run_dir / "0000000001.json").read_bytes()
            self.assertEqual(json.loads(content)["marker"], "first")

    def test_rebuild_head_matches_clean_write_head_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = open_run(directory, "run-1")
            run.append(1, record_bytes(1))
            run.append(2, record_bytes(2))
            expected = HeadProjection(
                last_sequence=2,
                last_record_file="0000000002.json",
                last_record=json.loads(record_bytes(2).decode("utf-8")),
            )
            run.write_head(expected)
            self.assertEqual(run.read_head(), expected)

            for scenario in ("missing", "corrupt"):
                head_path = run.run_dir / "_head.json"
                if scenario == "missing":
                    head_path.unlink()
                else:
                    head_path.write_text("{not json", encoding="utf-8")
                self.assertEqual(run.rebuild_head_from_scan(), expected)

    def test_read_head_returns_none_when_missing_or_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = open_run(directory, "run-1")
            self.assertIsNone(run.read_head())
            (run.run_dir / "_head.json").write_text("{broken", encoding="utf-8")
            self.assertIsNone(run.read_head())

    def test_lock_prevents_concurrent_sequence_collision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = open_run(directory, "run-1")
            used: list[int] = []
            used_lock = threading.Lock()

            def append_next(marker: str) -> None:
                with run.lock():
                    head = run.read_head()
                    if head is None:
                        next_seq = 1
                    else:
                        next_seq = head.last_sequence + 1
                    run.append(next_seq, record_bytes(next_seq, marker))
                    run.write_head(
                        HeadProjection(
                            last_sequence=next_seq,
                            last_record_file=f"{next_seq:010d}.json",
                            last_record=json.loads(record_bytes(next_seq, marker)),
                        )
                    )
                    with used_lock:
                        used.append(next_seq)

            threads = [
                threading.Thread(target=append_next, args=(f"t{index}",))
                for index in range(8)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(sorted(used), list(range(1, 9)))
            for seq in range(1, 9):
                self.assertTrue((run.run_dir / f"{seq:010d}.json").exists())

    def test_open_run_creates_missing_run_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run = open_run(directory, "genesis-run")
            self.assertTrue((Path(directory) / "runs" / "genesis-run").is_dir())


if __name__ == "__main__":
    unittest.main()
