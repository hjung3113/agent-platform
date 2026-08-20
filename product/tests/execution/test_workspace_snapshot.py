from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from execution.workspace_snapshot import snapshot_identity
from kernel.canonical import content_digest


class WorkspaceSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name) / "repo"
        self._init_repo(self.root)
        (self.root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        self._git(self.root, "commit", "-m", "initial fixture")

    def tearDown(self) -> None:
        self._temporary_directory.cleanup()

    @staticmethod
    def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )

    def _init_repo(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._git(path, "init")
        self._git(path, "config", "user.email", "snapshot-tests@example.invalid")
        self._git(path, "config", "user.name", "Workspace Snapshot Tests")

    def test_unchanged_workspace_is_deterministic(self) -> None:
        first = snapshot_identity(self.root)
        second = snapshot_identity(self.root)

        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)

    def test_tracked_staged_unstaged_and_untracked_components_are_independent(self) -> None:
        baseline = snapshot_identity(self.root)
        tracked = self.root / "tracked.txt"

        tracked.write_text("staged change\n", encoding="utf-8")
        self._git(self.root, "add", "tracked.txt")
        staged = snapshot_identity(self.root)
        self.assertNotEqual(staged.staged_digest, baseline.staged_digest)
        self.assertEqual(staged.unstaged_digest, baseline.unstaged_digest)
        self.assertEqual(staged.untracked_digest, baseline.untracked_digest)

        self._git(self.root, "restore", "--staged", "--worktree", "tracked.txt")
        tracked.write_text("unstaged change\n", encoding="utf-8")
        unstaged = snapshot_identity(self.root)
        self.assertEqual(unstaged.staged_digest, baseline.staged_digest)
        self.assertNotEqual(unstaged.unstaged_digest, baseline.unstaged_digest)
        self.assertEqual(unstaged.untracked_digest, baseline.untracked_digest)

        self._git(self.root, "restore", "--worktree", "tracked.txt")
        (self.root / "untracked.txt").write_text("untracked change\n", encoding="utf-8")
        untracked = snapshot_identity(self.root)
        self.assertEqual(untracked.staged_digest, baseline.staged_digest)
        self.assertEqual(untracked.unstaged_digest, baseline.unstaged_digest)
        self.assertNotEqual(untracked.untracked_digest, baseline.untracked_digest)

    def test_same_head_with_different_untracked_content_has_different_identity(self) -> None:
        other = Path(self._temporary_directory.name) / "other"
        self._git(Path(self._temporary_directory.name), "clone", str(self.root), str(other))

        (self.root / "untracked.txt").write_text("one\n", encoding="utf-8")
        (other / "untracked.txt").write_text("two\n", encoding="utf-8")
        first = snapshot_identity(self.root)
        second = snapshot_identity(other)

        self.assertEqual(first.head_commit, second.head_commit)
        self.assertNotEqual(first.untracked_digest, second.untracked_digest)
        self.assertNotEqual(first.digest, second.digest)

    def test_untracked_symlink_hashes_target_string_without_dereferencing(self) -> None:
        outside = Path(self._temporary_directory.name) / "outside.txt"
        outside.write_text("first outside content\n", encoding="utf-8")
        link = self.root / "outside-link"
        link.symlink_to(outside)

        first = snapshot_identity(self.root)
        outside.write_text("different outside content\n", encoding="utf-8")
        same_target = snapshot_identity(self.root)

        self.assertEqual(first.untracked_digest, same_target.untracked_digest)
        self.assertEqual(first.digest, same_target.digest)

        second_target = Path(self._temporary_directory.name) / "outside-second.txt"
        second_target.write_text("second target content\n", encoding="utf-8")
        link.unlink()
        link.symlink_to(second_target)
        different_target = snapshot_identity(self.root)

        self.assertNotEqual(first.untracked_digest, different_target.untracked_digest)
        self.assertNotEqual(first.digest, different_target.digest)

    def test_declared_generated_paths_are_digest_bound_and_sorted(self) -> None:
        first = snapshot_identity(self.root, ("generated/z.txt", "generated/a.txt"))
        same_paths_different_order = snapshot_identity(
            self.root, ("generated/a.txt", "generated/z.txt")
        )
        different = snapshot_identity(self.root, ("generated/other.txt",))

        self.assertEqual(first.generated_digest, same_paths_different_order.generated_digest)
        self.assertNotEqual(first.generated_digest, different.generated_digest)
        self.assertEqual(first.staged_digest, different.staged_digest)
        self.assertEqual(first.unstaged_digest, different.unstaged_digest)
        self.assertEqual(first.untracked_digest, different.untracked_digest)
        self.assertNotEqual(first.digest, different.digest)

    def test_uncommitted_change_inside_nested_repo_does_not_change_outer_snapshot(self) -> None:
        nested = self.root / "nested"
        self._init_repo(nested)
        nested_file = nested / "inner.txt"
        nested_file.write_text("nested committed\n", encoding="utf-8")
        self._git(nested, "add", "inner.txt")
        self._git(nested, "commit", "-m", "nested fixture")

        before = snapshot_identity(self.root)
        nested_file.write_text("nested uncommitted\n", encoding="utf-8")
        after = snapshot_identity(self.root)

        self.assertEqual(before.nested_repo_digest, after.nested_repo_digest)
        self.assertEqual(before.digest, after.digest)
        self.assertNotEqual(before.nested_repo_digest, content_digest([]))


if __name__ == "__main__":
    unittest.main()
