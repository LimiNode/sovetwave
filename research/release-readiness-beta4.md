# v0.5.0-beta.4 release readiness

Status: `draft` / readiness review only  
Prepared: `2026-11-12`

Candidate base: the already reviewed combined PR #71 tree
`394ca374b20e9b40b285d05492fa9a317ec86463`.

The candidate is prepared from the beta.3 release line. PR #70 is already an
ancestor of the combined #71 tree; it is not duplicated. PR #72 remains a
research-only branch and is not part of this production candidate.

Previous release: `v0.5.0-beta.3` at
`437c8ff116a96c69753bb7db40779d86fd892e00`.

Candidate identity: the exact head of the `release/beta4-prep` Draft PR. Read it
from `gh pr view --json headRefOid` and verify `git rev-parse HEAD` after
checkout. This tracked report cannot contain its own commit hash; the PR and
exact-head check records are the authoritative immutable candidate linkage.

## Decision

`GO` recommendation for publication review after the checks below pass and
the exact candidate head receives green CI. This document does not create a
tag, GitHub Release, or merge.

No model-backed evaluation was run for beta.4. Fixture counts and offline
tests verify repository structure and stated contracts; they do not measure a
general coding-agent quality improvement.

Integration review: `git merge-base --is-ancestor 60f52a985497869ddce861cc44eac7bf912f999a
394ca374b20e9b40b285d05492fa9a317ec86463` returned zero. Beta.3 is also an
ancestor of that combined tree. The actual beta.3-to-combined diff contains
only five production references and five behavioral fixture files. Inspection
found no duplicated new section or contradictory default: existing repository
contracts remain higher priority than the new-project fallback, orthogonal
state is not forced into one enum, intentionally shared state is distinct from
owner-thread state, and callback-target lifetime is separate from token lifetime.
The self-unsubscription fixture explicitly keeps the permitted teardown path
contract-dependent. No production rule was changed during release preparation.

Preferred integration: merge this release-prep PR once; it already contains
the combined #71 and #70 history. Do not merge #70 again. After owner
authorization and integration, close #70/#71 as superseded (or let GitHub mark
their already-reachable history merged). No PR closure or merge is performed
by this readiness pass.

## Release scope since beta.3

The production-facing changes in the combined #71 tree are:

- constructive C++ invariant guidance for state modeling, owner-thread versus
  intentionally shared state, and lifecycle-safe RAII registration tokens;
- a conditional teardown rule for self-unsubscription from an executing
  callback, without introducing general concurrency machinery;
- explicit hierarchical umbrella-first translation-unit guidance, including
  private-leaf, standalone-entry-point, brownfield, and CMake/data-domain
  boundaries;
- house-profile naming and repository-local `.worktrees`/build cleanup
  conventions, with established brownfield conventions preserved;
- focused behavioral fixtures for the above contracts and their negative
  cases.

Research-only benchmark harness work, executable oracles, trusted graders,
host enforcement adapters, and live A/B experiments remain outside the
production package. Beta.4 therefore makes no universal fail-closed security
claim and no claim of measured overall agent-performance improvement.

## Metadata

- `.claude-plugin/plugin.json` version: `0.5.0-beta.4`;
- newest `CHANGELOG.md` heading: `v0.5.0-beta.4 — 2026-11-12`;
- release notes preserve the research-only and no-performance-claim limits.

README's old optional-profile wording has been synchronized with the reviewed
new-project fallback. No other package version field needs a bump; eval suite
versions and voice corpus versions describe their own schemas/corpora.

## Public prerelease notes

Sovetwave beta.4 packages the combined C++ safety and project conventions:

- constructive invariants and explicit lifecycle/state transitions;
- owner-thread and intentionally shared-state boundaries;
- scoped registration tokens with contract-aware callback teardown;
- owning domain/subdomain umbrella first in independent translation units;
- new-project house conventions, workspace layout, CMake targets, and shared
  data-domain ownership, without imposing a migration on existing projects.

Limitations: no completed live A/B experiment or measured general coding-agent
performance improvement is claimed for beta.4. There is no production-grade
universal Claude host enforcement. Research-only checks do not establish a
universal fail-closed or security guarantee. Fixture counts are structural
coverage, not evidence of measured model benefit. This is a prerelease.

## Required release QA

Run these checks on the exact candidate head and record their observed output:

1. `python .github/scripts/validate_skill.py skills/sovetwave
   --release-metadata`;
2. `python evals/validate_evals.py`;
3. `python evals/test_voice_cards.py`;
4. `python tests/behavioral/test_harness.py`;
5. the focused offline tests for experiment readiness, fixtures, executable
   oracle, and host pre-execution guard;
6. the full available `pytest` suite;
7. PowerShell and POSIX installer smoke tests, including fresh install and
   upgrade/reinstallation checks where the host permits them;
8. package-content inspection, `git diff --check`, and exact-head GitHub CI.

Observed local results on 2026-11-12 (the release-prep payload based on the exact
combined tree above; Windows/Python 3.11, POSIX smoke via Git Bash):

| Command/check | Result |
| --- | --- |
| `python .github/scripts/validate_skill.py skills/sovetwave --release-metadata` | PASS |
| `python evals/validate_evals.py` | `33 suites / 297 cases` |
| `python evals/test_voice_cards.py` | PASS, deterministic 2-card selection |
| `python tests/behavioral/test_harness.py` | `120 tests`, OK |
| `python tests/behavioral/test_experiment_readiness.py` | `12 tests`, OK |
| `python tests/behavioral/test_experiment_fixtures.py` | `11 tests`, OK |
| `python tests/behavioral/test_executable_oracle.py` | `7 tests`, OK |
| `python tests/behavioral/test_host_pre_execution_guard.py` | `20 tests`, OK |
| `python -m pytest -q` | `223 passed, 41 subtests passed` |
| `./tests/installers/smoke.ps1` | PASS, Windows PowerShell |
| `bash tests/installers/smoke.sh` | PASS, Git Bash; not native Linux evidence |
| `git diff --check` | PASS |

Both installer smoke suites cover fresh user/repository installation, refusal
to overwrite without authorization, forced reinstallation, and rollback after
injected failures at each of three targets. They do not invoke Codex, Claude,
or any model. Native Ubuntu/Windows checks remain an exact-head CI gate; the
previous #71 CI result is not substituted for the new release head.

The expected eval registry after the combined tree is `33 suites / 297 cases`.
If a platform-specific installer check is unavailable, record it as
`not checked` and rely only on the corresponding exact-head CI result; do not
substitute an unrelated local check.

## Publication gate

Publication is allowed only when the candidate is refreshed onto the final
release `main`, metadata agrees, all applicable local checks pass, and exact-
head CI is green. The owner must separately authorize the tag and GitHub
Release. The beta.3 tag and release are not modified.

## Post-release research boundary

PR #72 should continue separately with real agent-host tool isolation,
candidate-versus-trusted grading separation, baseline attestation, complete
tool trajectories, and a small live pilot only after explicit authorization.
