# Sovetwave beta.3 practical-effectiveness evaluation

This directory contains an offline preflight for comparing one coding agent
with and without the combined post-beta.3 Sovetwave policy candidate. It is a
research-only artifact. It does not call a model, start an agent host, or modify
the production skill. Trusted reference, defective, and starter controls can
be compiled and run only in the Docker boundary described in `executor.md`.

The protocol is intentionally fail-closed. The task contracts and grading
gates have executable controls, but live evaluation remains blocked until a
reviewed agent bridge binds model and host identity, permissions, clean arm
environments, tool traces, and candidate artifact provenance.

Files:

- `manifest.json` — frozen release identity, arms, allocation, gates, and
  explicit blockers;
- `protocol.md` — execution order, grading rules, isolation boundary, and
  pilot budget;
- `fixtures/` — six task specifications bound to executable fixture trees;
- `executable/` — starter/reference repositories, independent test sources,
  content lock, and a network-disabled container entry point;
- `preflight.py` — offline identity/allocation checks, deterministic Git
  fixture preparation, image provisioning, and trusted-control selftest;
- `validation.md` — observed results, six-task readiness matrix, and blockers.

The historical production reference is beta.3 commit
`437c8ff116a96c69753bb7db40779d86fd892e00`. The candidate combines that tree
with PR #70 and PR #71 at the unmerged integration commit recorded in
`manifest.json`. Both skill-tree identities are preserved; the candidate hash
is not presented as the published beta.3 hash.

The expected offline disposition is `HOLD`: design work may be reviewed, but
no live comparison may start until the execution preflight closes the listed
blockers.
