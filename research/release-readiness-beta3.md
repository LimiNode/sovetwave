# v0.5.0-beta.3 release readiness

Status: `draft` / readiness review only

Prepared: `2026-11-08`

Candidate base after PR #68 integration:
`e71abf53a2390ecab02f76adfdaa9434fc6c7b96` (`origin/main`)

Prepared candidate HEAD: the exact PR head; verify with `git rev-parse HEAD`
after checkout. The PR metadata is the authoritative record because this file
is part of the commit whose hash it would otherwise contain.

Previous release: `v0.5.0-beta.2` at
`efb48ec0b10dfbc8b6ca198b5c1b3b09f49be820`

## Decision

`GO` recommendation for final publication review; publication itself remains
pending a separate owner command.

This branch prepares the metadata and release notes for `v0.5.0-beta.3`; it
does not create a tag or GitHub Release. PR #68 (Claude enforcement feasibility
v2) is now integrated in the candidate tree through merge commit
`e71abf53a2390ecab02f76adfdaa9434fc6c7b96`; its materials remain design-only
and do not add a production Claude adapter.

The candidate is otherwise a metadata-only release preparation. No model
evaluation, host experiment, provider request, production Claude adapter, or
historical benchmark rewrite is part of this release check.

The release candidate intentionally preserves the activation boundary: the
repository documents when the Sovetwave skill is available, but no new
model-backed natural-activation run was performed here. That capability is not
claimed as newly measured evidence for beta.3.

## Release scope since beta.2

The production-facing skill changes between the previous tag and this base
include:

- stronger evidence discipline for authored architecture models, source
  entailment, runtime observations, executable documentation, and consumer
  paths;
- C++ guidance for new-project umbrella dependency topology, private leaves,
  package boundaries, installed consumers, and explicit brownfield exceptions;
- optional task contracts and the repository's default `.worktrees/<task-name>`
  convention for isolated multi-stage work;
- explicit treatment of specialization invariants, benchmark semantic parity,
  mutation completeness, and declared compatibility boundaries;
- expanded deterministic fixtures and CI checks for repository-grounded
  validation.

Research notes, host-hook evidence, and offline pilots remain research
artifacts. They are not advertised as a production enforcement feature.

## Release metadata prepared

- `.claude-plugin/plugin.json` version: `0.5.0-beta.3`;
- newest `CHANGELOG.md` heading: `v0.5.0-beta.3 — 2026-11-08`;
- release notes explicitly state that host enforcement adapters and
  research-only experiments are outside the production skill.

The release policy keeps research notes and internal curation history out of
the public changelog. A GitHub prerelease body should repeat the same scope
and limitations rather than claim a Claude-specific security boundary.

## Combined-tree checks at the prepared candidate

The following checks passed again after merging #68 into the release branch:

| Check | Result |
|---|---|
| `validate_skill.py --release-metadata` | PASS |
| `evals/validate_evals.py` | `33 suites / 281 cases` |
| `evals/test_voice_cards.py` | PASS, deterministic 2-card result |
| `tests/behavioral/test_harness.py` | `120 tests`, `OK` |
| `test_experiment_readiness.py` | `12 tests`, `OK` |
| `test_experiment_fixtures.py` | `11 tests`, `OK` |
| `test_executable_oracle.py` | `7 tests`, `OK` |
| `test_host_pre_execution_guard.py` | `20 tests`, `OK` |
| `python -m pytest -q` | `223 passed, 41 subtests passed` |
| PowerShell installer smoke | PASS |
| POSIX installer smoke | PASS |
| `git diff --check` | PASS |

The post-merge exact-head GitHub Actions run is recorded in the final PR
metadata. A passing local suite does not substitute for that CI boundary.

The combined tree contains the #68 research files and merge commit
`e71abf53a2390ecab02f76adfdaa9434fc6c7b96`; it still contains no production
Claude enforcement implementation. The documented `HOLD` boundary for host
enforcement and the absence of new model-backed activation evidence remain
known release limitations.

## Required checks on the final release candidate

The final candidate check set is:

1. `python .github/scripts/validate_skill.py skills/sovetwave
   --release-metadata`;
2. `python evals/validate_evals.py`;
3. `python evals/test_voice_cards.py`;
4. `python tests/behavioral/test_harness.py`;
5. `python tests/behavioral/test_experiment_readiness.py`;
6. `python tests/behavioral/test_experiment_fixtures.py`;
7. `python tests/behavioral/test_executable_oracle.py`;
8. `python tests/behavioral/test_host_pre_execution_guard.py`;
9. the full available offline test suite and both installer smoke tests;
10. `git diff --check`, package-content inspection, and exact-head GitHub CI.

The model-backed behavioral harness is not a release prerequisite for this
metadata-only check and must not be represented as having run. If an offline
check or installer check is unavailable on the local platform, record that
fact and rely on the corresponding exact-head CI job rather than substituting
an unrelated test.

## Publication gate

The `GO` recommendation is valid only while all of these remain true:

- PR #68 is merged and its merge SHA is recorded;
- this branch is refreshed onto that final release `main`;
- plugin metadata and the newest changelog heading match;
- all applicable offline and installer checks pass;
- exact-head GitHub CI is green on the release candidate; and
- release notes preserve the limitations: no production Claude enforcement
  adapter, no universal hook coverage, and no claim that research-only host
  observations are fail-closed security evidence.

These conditions are satisfied for the current candidate. The tag and GitHub
Release are still intentionally absent; the recommendation does not itself
authorize publication or merge of PR #69.
