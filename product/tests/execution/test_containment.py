from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from kernel.admission import _resolve_inside


class ContainmentTest(unittest.TestCase):
    """Adversarial fixtures for `admission._resolve_inside` (M3 plan §4)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        # macOS temp dirs commonly sit behind a symlink (/tmp -> /private/tmp);
        # resolve the root once and reuse the resolved root everywhere.
        self.root = Path(self._tmp.name).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.outside = Path(tempfile.mkdtemp(prefix="outside-")).resolve()
        self.addCleanup(shutil.rmtree, self.outside, ignore_errors=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # --- escape cases (must fail closed) ---

    def test_plain_traversal_escape_rejected(self) -> None:
        """§4 fixture 1: ../../etc/passwd-style traversal escapes root."""
        candidate = self.root / "work" / ".." / ".." / ".." / "etc" / "passwd"
        self.assertIsNone(_resolve_inside(self.root, candidate))

    def test_symlink_inside_root_pointing_outside_rejected(self) -> None:
        """§4 fixture 2: symlink inside root whose target is outside root."""
        target = self.outside / "secret.txt"
        target.write_text("outside")
        link = self.root / "escape-link"
        os.symlink(target, link)
        self.assertIsNone(_resolve_inside(self.root, link))

    def test_chained_symlink_escape_rejected(self) -> None:
        """§4 fixture 3: symlink chained through another symlink ending outside root."""
        outside_file = self.outside / "deep-target.txt"
        outside_file.write_text("outside")
        mid_link = self.outside / "mid-link"
        os.symlink(outside_file, mid_link)
        link = self.root / "chain-link"
        os.symlink(mid_link, link)
        self.assertIsNone(_resolve_inside(self.root, link))

    def test_nested_repo_shaped_directory_containment(self) -> None:
        """§4 fixture 4: nested-repo-shaped dirs get ordinary containment treatment.

        A nested repo inside root is admitted; a symlink from inside root to a
        git-shaped directory outside root is rejected by the same mechanism as
        fixtures 2/3 (`_resolve_inside` has no candidate_paths concept of its own).
        """
        nested_inside = self.root / "vendor-repo"
        (nested_inside / ".git").mkdir(parents=True)
        (nested_inside / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
        resolved = _resolve_inside(self.root, nested_inside / "README.md")
        self.assertEqual(resolved, nested_inside / "README.md")

        nested_outside = self.outside / "evil-repo"
        (nested_outside / ".git").mkdir(parents=True)
        link = self.root / "repo-link"
        os.symlink(nested_outside, link)
        self.assertIsNone(_resolve_inside(self.root, link))

    def test_parent_directory_symlink_escape_rejected(self) -> None:
        """§4 fixture 5: textually inside root, realpath outside via parent symlink."""
        outside_dir = self.outside / "real-parent"
        outside_dir.mkdir()
        linked_parent = self.root / "linked-parent"
        os.symlink(outside_dir, linked_parent)
        candidate = linked_parent / "payload.txt"
        self.assertIsNone(_resolve_inside(self.root, candidate))

    def test_symlink_loop_fails_closed(self) -> None:
        """§4 fixture 6: symlink loop must return None, not crash the caller."""
        loop = self.root / "self-loop"
        os.symlink(loop, loop)
        self.assertIsNone(_resolve_inside(self.root, loop))

        a = self.root / "loop-a"
        b = self.root / "loop-b"
        os.symlink(b, a)
        os.symlink(a, b)
        self.assertIsNone(_resolve_inside(self.root, a))

    # --- legitimate-admit cases (must stay admitted) ---

    def test_nonexistent_file_with_existing_parent_admitted(self) -> None:
        """§4 legitimate case: not-yet-created write target under an existing parent."""
        parent = self.root / "src"
        parent.mkdir()
        candidate = parent / "new-file.txt"
        self.assertEqual(_resolve_inside(self.root, candidate), candidate)

    def test_fully_nonexistent_path_admitted(self) -> None:
        """§4 legitimate case: parent also missing, resolved path still inside root."""
        candidate = self.root / "new-dir" / "deeper" / "output.txt"
        self.assertEqual(_resolve_inside(self.root, candidate), candidate)

    def test_ordinary_nested_subdirectory_admitted(self) -> None:
        """§4 legitimate case: unambiguously-inside nested path resolves fine."""
        nested = self.root / "pkg" / "sub"
        nested.mkdir(parents=True)
        candidate = nested / "module.txt"
        candidate.write_text("inside")
        self.assertEqual(_resolve_inside(self.root, candidate), candidate)


if __name__ == "__main__":
    unittest.main()
