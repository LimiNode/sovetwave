# Executable preflight validation record

Status: trusted-control preflight PASS; live evaluation HOLD. Date: 2026-11-11.
No model calls, agent sessions, or model-generated program executions occurred.

## Identities and coverage corrections

Skill trees were recomputed from raw Git blob bytes, sorted repository-relative
UTF-8 paths, and actual `00` NUL separators:

| Tree | Commit | SHA-256 |
| --- | --- | --- |
| Published beta.3 | `437c8ff116a96c69753bb7db40779d86fd892e00` | `f2c7c17a96d0fb4399617b42207fa1c6cd5a5c3c51815a35118d92170c9d3231` |
| Combined #70/#71 | `394ca374b20e9b40b285d05492fa9a317ec86463` | `2d696b9b57d000c6cd4e9c7ecd283a22209cfdfc93e1cabcc680b377df6a5044` |

Both trees contain 38 files. Earlier hashes used textual backslash-zero rather
than NUL and were incorrect; manifest preserves them as provenance, not accepted
identities. The combined candidate itself is unchanged.

Automatic house fallback and new working-area layout are assigned to greenfield.
Brownfield tests preservation of established conventions. Six tasks and the
36 + 12 + 12 = 60 call ceiling remain unchanged; seeded allocation contains 30
complete pairs, with balanced arm positions within each experiment.

Contracts were narrowed to match executable evidence before any model run:
ownership is synchronous token registration (not asynchronous completion);
reentrancy is a one-shot worker with external teardown; state close is immediate
(no unimplemented Closing phase); filesystem validation rejection, not arbitrary
I/O failure, is side-effect-free. No configuration override or data-domain
behavior is claimed by these small fixtures. This prevents broader contract
prose from being reported as tested coverage.

## Six-task readiness matrix

Every row has a pinned starter, exact task prompt, reference and mutant, trusted
test source, content digest and deterministic fresh-copy setup. Provenance PASS
below refers only to fixtures/controls; model-run provenance is NOT_EXECUTED.

| Task | Fixture | Bounded oracle controls | Container isolation | Fixture provenance | Remaining observation blockers |
| --- | --- | --- | --- | --- | --- |
| ownership | prepared | PASS: reference accepted; mutant/starter rejected | PASS | PASS | bridge/traces; no async/concurrent lifetime claim |
| reentrancy | prepared | PASS: reference accepted; held-lock mutant times out; starter rejected | PASS | PASS | bridge/traces; external teardown only, no TSan claim |
| state | prepared | PASS: reference accepted; invalid-send mutant/starter rejected | PASS | PASS | bridge/traces; representation economy needs review |
| brownfield | prepared | PASS: reference accepted; parser mutant/starter rejected | PASS | PASS | helper reuse and actual scratch/build locations need trace/review |
| greenfield | prepared | PASS: reference accepted; installed-package mutant/starter rejected | PASS | PASS | complete naming/target rationale needs review; directory presence is not a real worktree |
| boundary | prepared | PASS: reference accepted; early-write mutant/starter rejected | PASS | PASS | bridge/traces; no concurrent replacement or I/O rollback claim |

Greenfield inspects actual submitted paths/ignore rules and first includes, then
builds, installs, and runs an independent consumer. It checks imported STATIC/
INTERFACE target types and compiles range-predicate assertions through a separate
installed utility-only consumer without the compiled component. Other tasks compile trusted
tests against the submitted API using C++17 plus ASan/UBSan. Protected-file
hashes reject unrelated edits. Boundary additionally checks a rejected
traversal's syscalls for write attempts. Tests establish only exercised paths.

## Isolation controls and evidence

Full machine-readable evidence is `evidence/control-report.json`, bound to the
image and content lock in `runtime-preflight.json`. Observed GCC is 13.4.0 and
CMake is 3.25.1. The image is immutable by ID; apt provisioning is not snapshot-
pinned and bit-for-bit rebuild reproducibility is not claimed.

- Six references PASS; six mutants FAIL at their specified condition; six
  starters FAIL. No missing oracle check receives PASS.
- Non-root UID, read-only root, dropped capabilities, no-new-privileges,
  seccomp, absent/denied host paths/socket, loopback-only network and blocked
  external connection: PASS.
- Cgroup CPU/memory/process settings, denied excessive forks and oversized
  file: PASS. Memory control is killed with `OOMKilled=true` and exit 137;
  its individual process FAIL is the expected negative-control result.
- Hung parent/child container is killed on timeout, stopped and removed;
  fresh-container reset probe passes. Writable `/work` is explicitly executable
  tmpfs; Docker's default noexec tmpfs was detected and corrected.
- A prior low file-size limit prevented GCC from producing binaries; corrected
  to 64 MiB per file. Neither configuration defect counted as a task failure.

These controls validate the host boundary under the tested Docker setup, not
tamper-resistant grading against adversarial programs. Candidate and evaluator
currently share a UID and image-visible tests/references. No host-side candidate CLI is
exposed. Trusted result collection and generation-workspace secrecy must be
reviewed before model-generated submissions are enabled.

## Offline checks and decision

- `preflight.py --offline`: raw skill identities, 36 locked files and 30 pairs PASS;
- `preflight.py --selftest --image <runtime-preflight image>`: control suite PASS;
- focused `test_cpp_preflight.py`: 12 tests PASS;
- full `python -m pytest -q`: 235 passed, 41 subtests passed;
- `python evals/validate_evals.py`: 33 suites / 281 cases;
- skill metadata, voice-card selector and `git diff --check`: PASS.

Focused tests cover NUL/raw bytes, content-lock drift, duplicate/missing pairs,
counterbalance, forbidden mounts/env forwarding, unsafe archives, missing or
duplicate checks, distinct statuses, and repeatable Git setup without resets.
GitHub workflow now runs these offline tests. Docker controls are separately
recorded local checks, not implied by the three existing CI jobs.

The unchanged combined candidate previously passed 33 suites / 297 cases,
behavioral harness 120 tests and pytest 223 tests / 41 subtests. This research
branch is based on beta.3, retaining 281 cases; it refers to the candidate by
commit/hash, not by its own production tree.

Final verdict: **HOLD** for live evaluation. `runtime-preflight.json` records
unbound model/host/budget, baseline isolation and agent-tool routing gaps. The
next step is one model-free bridge/security preflight, not more policy rules or
model runs. No merge, tag, release or main update is authorized by this record.
