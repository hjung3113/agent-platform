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

    def test_generated_path_content_change_changes_digest(self) -> None:
        """PR-review fix: generated_digest must hash content, not only names.

        A declared generated path is often Git-ignored; before this fix,
        only the path name was hashed, so creating/editing/deleting the
        actual artifact never changed the digest — distinct Result content
        could share one identity. Ignore the path via .gitignore so it never
        enters staged/unstaged/untracked state and only generated_digest can
        observe it.
        """

        (self.root / ".gitignore").write_text("generated/\n", encoding="utf-8")
        self._git(self.root, "add", ".gitignore")
        self._git(self.root, "commit", "-m", "ignore generated/")
        generated_dir = self.root / "generated"
        generated_dir.mkdir()
        declared = ("generated/output.bin",)

        absent = snapshot_identity(self.root, declared)
        (generated_dir / "output.bin").write_bytes(b"first artifact bytes")
        first_content = snapshot_identity(self.root, declared)
        (generated_dir / "output.bin").write_bytes(b"different artifact bytes")
        second_content = snapshot_identity(self.root, declared)

        self.assertNotEqual(absent.generated_digest, first_content.generated_digest)
        self.assertNotEqual(first_content.generated_digest, second_content.generated_digest)
        self.assertNotEqual(absent.digest, first_content.digest)
        self.assertNotEqual(first_content.digest, second_content.digest)
        # Ignored, so staged/unstaged/untracked never see the artifact at all.
        self.assertEqual(absent.untracked_digest, second_content.untracked_digest)

    def test_uncommitted_change_inside_nested_repo_changes_outer_snapshot(self) -> None:
        """PR-review fix: a nested repo's dirty state must be visible outside.

        An earlier version bound only the nested repo's commit id, so an
        uncommitted change inside it never changed the outer digest — the
        runtime could consume different nested content across two snapshots
        that claimed the same identity. Nested identity now recurses through
        the nested repo's own full ``snapshot_identity``, so its dirty state
        is bound transitively.
        """

        nested = self.root / "nested"
        self._init_repo(nested)
        nested_file = nested / "inner.txt"
        nested_file.write_text("nested committed\n", encoding="utf-8")
        self._git(nested, "add", "inner.txt")
        self._git(nested, "commit", "-m", "nested fixture")

        before = snapshot_identity(self.root)
        nested_file.write_text("nested uncommitted\n", encoding="utf-8")
        after = snapshot_identity(self.root)

        self.assertNotEqual(before.nested_repo_digest, after.nested_repo_digest)
        self.assertNotEqual(before.digest, after.digest)
        self.assertNotEqual(before.nested_repo_digest, content_digest([]))

        # Committing the same change back to committed state (same content,
        # re-committed) restores an equal nested identity, since it is the
        # nested repo's own snapshot digest, not merely "dirty vs. clean".
        self._git(nested, "add", "inner.txt")
        self._git(nested, "commit", "-m", "nested fixture update")
        after_commit = snapshot_identity(self.root)
        self.assertNotEqual(before.nested_repo_digest, after_commit.nested_repo_digest)


if __name__ == "__main__":
    unittest.main()
