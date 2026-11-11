# Sovetwave beta.3 practical-effectiveness evaluation

This directory contains an offline protocol for comparing one coding agent
with and without the combined post-beta.3 Sovetwave policy candidate. It is a
research-only artifact. It does not call a model, start an agent host, execute
generated code, or modify the production skill.

The protocol is intentionally fail-closed. The task contracts and grading
gates are defined here, but execution remains blocked until a separate
preflight binds real fixture repositories, an isolated executor, a model and
host identity, permissions, tool traces, and artifact provenance.

Files:

- `manifest.json` — frozen release identity, arms, allocation, gates, and
  explicit blockers;
- `protocol.md` — execution order, grading rules, isolation boundary, and
  pilot budget;
- `fixtures/` — six contract-level synthetic task specifications. They are
  not executable candidate repositories yet; the preflight must either bind
  reviewed repositories to them or mark the task `NOT_EXECUTED`.

The historical production reference is beta.3 commit
`437c8ff116a96c69753bb7db40779d86fd892e00`. The candidate combines that tree
with PR #70 and PR #71 at the unmerged integration commit recorded in
`manifest.json`. Both skill-tree identities are preserved; the candidate hash
is not presented as the published beta.3 hash.

The expected offline disposition is `HOLD`: design work may be reviewed, but
no live comparison may start until the execution preflight closes the listed
blockers.
