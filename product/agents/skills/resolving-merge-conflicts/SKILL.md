---
name: resolving-merge-conflicts
description: Use when resolving an in-progress git merge or rebase conflict by tracing both sides to their source intent.
---

# Resolving Merge Conflicts

1. **See the current state.** Inspect merge/rebase state, history, and conflicting files.
2. **Find primary sources.** Understand why each side changed: commit messages, PRs, issues/specs, and governing design.
3. **Resolve each hunk by intent.** Preserve both intents where compatible. Where incompatible, choose the result that matches the merge/rebase goal and governing authority; do not invent unrelated behaviour.
4. **Run the project's checks.** Use the relevant type/static checks, focused tests, full regression suite as justified, and formatting only where it does not create drive-by diff.
5. **Finish the operation.** Stage the intended resolutions and continue/commit the merge or rebase.

Do not abort merely to avoid a difficult conflict. If evidence shows the merge/rebase itself targets the wrong history, violates scope, or cannot preserve required invariants, stop and surface that as the actual problem rather than forcing a synthetic resolution.

Remote push/merge or other external effects remain separately authorized by project policy.
