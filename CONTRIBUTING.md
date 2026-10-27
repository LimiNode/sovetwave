# Contributing

## Isolated worktrees

When a change needs an isolated branch, create new Git worktrees under
`.worktrees/<task-name>` by default. Use another location only when the user
or an established repository constraint specifies one.

Before creating a worktree, inspect `git worktree list --porcelain` and confirm
that the requested branch is not already checked out elsewhere. Keep one
active worktree per branch.

Before removing a worktree, inspect the exact target reported by
`git worktree list --porcelain` with
`git -C <path> status --short --untracked-files=all --ignored`. This check must
cover staged, unstaged, untracked, and ignored files that may contain local
user data. Removal requires explicit authorization and a clean, no-longer-used
target. Use the ordinary `git worktree remove <path>` without `--force`; do not
use `rm -rf`, `Remove-Item -Recurse -Force`, `git worktree remove --force`, or
`git worktree prune` for routine cleanup. A merged or closed PR does not by
itself authorize deleting its worktree.

Existing worktrees outside `.worktrees/` remain valid; do not move or delete
them merely to enforce this convention. A simple change that is safe in the
current checkout does not require creating a worktree.

The repository-root `.worktrees/` directory is Git-ignored to keep local
worktrees out of ordinary staging and status output. This does not replace
worktree-aware cleanup or tooling exclusions.
