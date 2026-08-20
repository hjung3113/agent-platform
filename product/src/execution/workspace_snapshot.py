"""Deterministic identity for the effective state of a Git workspace."""

from __future__ import annotations

import base64
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from kernel.canonical import content_digest


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """Structured evidence and identity for one effective workspace snapshot."""

    root: str
    head_commit: str | None
    staged_digest: str
    unstaged_digest: str
    untracked_digest: str
    generated_digest: str
    nested_repo_digest: str

    def to_canonical_value(self) -> dict[str, object]:
        return {
            "root": self.root,
            "head_commit": self.head_commit,
            "staged_digest": self.staged_digest,
            "unstaged_digest": self.unstaged_digest,
            "untracked_digest": self.untracked_digest,
            "generated_digest": self.generated_digest,
            "nested_repo_digest": self.nested_repo_digest,
        }

    @property
    def digest(self) -> str:
        """Stable content identity for all fields in this snapshot."""

        return content_digest(self.to_canonical_value())


def _run_git(arguments: Sequence[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", *arguments],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ValueError("git executable is unavailable") from exc
    except OSError as exc:
        raise ValueError(f"unable to run git in workspace {cwd}: {exc}") from exc
    return completed.stdout


def _require_git_worktree(root: Path) -> None:
    try:
        result = _run_git(("rev-parse", "--is-inside-work-tree"), cwd=root)
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"workspace root is not a git worktree: {root}") from exc
    if result.strip() != "true":
        raise ValueError(f"workspace root is not a git worktree: {root}")


def _head_commit(root: Path) -> str | None:
    try:
        output = _run_git(("rev-parse", "HEAD"), cwd=root).strip()
    except subprocess.CalledProcessError:
        return None
    return output or None


def _find_nested_repositories(root: Path) -> list[Path]:
    nested: list[Path] = []
    try:
        walker = os.walk(root, topdown=True, followlinks=False)
        for current, directories, files in walker:
            current_path = Path(current)
            has_git_entry = ".git" in directories or ".git" in files
            if current_path == root:
                if ".git" in directories:
                    directories.remove(".git")
                continue
            if has_git_entry:
                nested.append(current_path)
                directories[:] = []
    except OSError as exc:
        raise ValueError(f"unable to inspect nested repositories under {root}") from exc
    return sorted(nested, key=lambda path: path.relative_to(root).as_posix())


def _nested_repository_entries(root: Path, nested_paths: Sequence[Path]) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for nested_path in nested_paths:
        try:
            inside_worktree = _run_git(
                ("-C", str(nested_path), "rev-parse", "--is-inside-work-tree"),
                cwd=root,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"nested path is not a git worktree: {nested_path}") from exc
        if inside_worktree.strip() != "true":
            raise ValueError(f"nested path is not a git worktree: {nested_path}")

        try:
            commit = _run_git(
                ("-C", str(nested_path), "rev-parse", "HEAD"), cwd=root
            ).strip()
        except subprocess.CalledProcessError:
            commit = None

        entries.append(
            {
                "path": nested_path.relative_to(root).as_posix(),
                "commit": commit or None,
            }
        )
    return entries


def _is_within_nested_repository(path: Path, nested_paths: Sequence[Path]) -> bool:
    return any(path == nested_path or nested_path in path.parents for nested_path in nested_paths)


def _untracked_content_or_link(path: Path) -> str:
    if os.path.islink(path):
        try:
            return os.readlink(path)
        except OSError as exc:
            raise ValueError(f"unable to read untracked symlink: {path}") from exc

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"unable to read untracked file: {path}") from exc

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return "base64:" + base64.b64encode(raw).decode("ascii")


def _untracked_entries(root: Path, nested_paths: Sequence[Path]) -> list[dict[str, str]]:
    status = _run_git(
        ("status", "--porcelain=v1", "--untracked-files=all", "-z"), cwd=root
    )
    paths = sorted(
        record[3:]
        for record in status.split("\0")
        if record.startswith("?? ")
    )

    entries: list[dict[str, str]] = []
    for relative_name in paths:
        relative_path = Path(relative_name)
        if _is_within_nested_repository(relative_path, nested_paths):
            continue

        path = root / relative_path
        if not os.path.islink(path) and path.is_dir():
            continue
        if not os.path.isfile(path) and not os.path.islink(path):
            raise ValueError(f"untracked path is not a readable file: {path}")
        entries.append(
            {
                "path": relative_path.as_posix(),
                "content_or_link": _untracked_content_or_link(path),
            }
        )
    return entries


def snapshot_identity(
    root: Path, declared_generated_paths: tuple[str, ...] = ()
) -> WorkspaceSnapshot:
    """Collect and return the effective identity of a Git workspace."""

    resolved_root = Path(root).resolve()
    if not resolved_root.is_dir():
        raise ValueError(f"workspace root is not a directory: {resolved_root}")
    _require_git_worktree(resolved_root)

    nested_paths = _find_nested_repositories(resolved_root)
    nested_entries = _nested_repository_entries(resolved_root, nested_paths)
    untracked_entries = _untracked_entries(resolved_root, nested_paths)

    return WorkspaceSnapshot(
        root=str(resolved_root),
        head_commit=_head_commit(resolved_root),
        staged_digest=content_digest(
            _run_git(("diff", "--cached"), cwd=resolved_root)
        ),
        unstaged_digest=content_digest(_run_git(("diff",), cwd=resolved_root)),
        untracked_digest=content_digest(untracked_entries),
        generated_digest=content_digest(list(sorted(declared_generated_paths))),
        nested_repo_digest=content_digest(nested_entries),
    )
