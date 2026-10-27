# Contributing

## Isolated worktrees

When a change needs an isolated branch, create new Git worktrees under
`.worktrees/<task-name>` by default. Use another location only when the user
or an established repository constraint specifies one.

Keep one active worktree per branch and check `git worktree list` before
creating or removing one. Existing worktrees outside `.worktrees/` remain
valid; do not move or delete them merely to enforce this convention. Remove an
old worktree only after its branch and uncommitted changes are no longer in
use.

The `.worktrees/` directory is ignored so local worktree contents cannot enter
the repository's change set.
