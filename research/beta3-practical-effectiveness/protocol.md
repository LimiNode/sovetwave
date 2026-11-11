# Offline protocol

## Question and non-goals

The primary question is whether the released Sovetwave skill improves
engineering correctness, completeness, and maintainability on small C++17
coding tasks without introducing unnecessary abstractions or regressions.

This protocol does not measure the value of individual rules, prove a general
model capability, or authorize a release. It does not use the post-beta policy
PRs as part of the treatment. The treatment is the frozen beta.3 release only.

## Arms and identity

The primary comparison uses the same agent, model, host, tool surface,
permissions, task input, environment, timeout, and repetition plan in two arms:

1. `baseline` — no Sovetwave skill loaded;
2. `sovetwave-beta3-explicit` — the released beta.3 skill tree loaded and
   activation recorded in the host/tool trace.

Natural activation is a separate 12-call subset over two activation-sensitive
tasks. It is not pooled with the explicit primary comparison. A final answer
cannot prove activation; a missing host trace is `unavailable`.

The grounded tool-use subset is another separate 12-call subset over the two
tasks that require an executable oracle. It is not scored as execution success
without per-call traces and an isolated executor result.

## Task inventory

Six small synthetic task contracts cover the following risks:

| ID | Boundary | Primary executable evidence |
| --- | --- | --- |
| `cpp-ownership-callback` | owner and callback lifetime | build, focused lifetime tests, late-callback negative case |
| `cpp-reentrancy-teardown` | callback reentrancy and shutdown | subprocess timeout, callback-outside-lock check, teardown tests |
| `cpp-state-transitions` | valid and invalid lifecycle transitions | compile/tests for accepted and rejected operations |
| `cpp-brownfield-reuse` | brownfield reuse and unnecessary abstraction | repository tests plus bounded diff/contract review |
| `cpp-greenfield-library` | CMake target and public API boundary | clean build, install, and consumer test |
| `cpp-untrusted-boundary` | validation before a filesystem side effect | sandbox trace proving rejection before mutation |

Each fixture defines success, boundary, failure, and verification outputs. A
short happy-path implementation is therefore a failed completeness gate, not a
smaller successful answer. `fixtures/*.json` contain the contract-level
requirements and the oracle boundary for later binding.

## Grading gates

Grade each observation independently on these hard gates:

- **functionality** — required operation and public contract pass;
- **completeness** — normal, boundary, failure, and verification paths pass;
- **safety** — no confirmed lifetime, reentrancy, or untrusted-input defect;
- **compatibility** — existing brownfield contract or installed consumer stays
  valid;
- **economy** — unnecessary abstractions, states, dependencies, and unrelated
  edits are recorded only after the hard gates pass.

Allowed statuses are `PASS`, `FAIL`, `INVALID`, `NOT_EXECUTED`, and
`NOT_ASSESSABLE`. Cost, token count, and code size never compensate for a
hard-gate failure. Paired deltas require matching arm, task, repetition,
model, environment, and runtime identity.

## Isolation and provenance requirements

Before any model call, the preflight must provide:

- a clean synthetic repository copy outside the ordinary Sovetwave checkout;
- a reviewed executor with network disabled, bounded CPU/time/memory, and no
  developer credentials;
- immutable task, prompt, skill-tree, model, host, and environment hashes;
- per-call tool trajectories, generated-file manifest, stdout/stderr, exit
  status, and oracle result;
- a cleanup policy that does not delete unrelated worktrees or artifacts.

Generated C++ must never run in the ordinary repository or developer shell.
Missing traces, missing artifact provenance, a broken isolation boundary, or an
unbound fixture changes the observation to `NOT_EXECUTED`/`NOT_ASSESSABLE`; it
does not become a passing result by inference.

## Allocation and stopping

The primary pilot is 6 tasks × 3 repetitions × 2 arms = 36 model calls. The
natural-activation subset adds 2 tasks × 3 repetitions × 2 arms = 12 calls,
and the grounded tool-use subset adds another 12 calls. The proposed ceiling is
60 calls total; no calls are authorized by this document.

Use counterbalanced seeded blocks and freeze the order before execution. Stop
before comparison if model/host/permissions/environment differ, if any paired
identity is incomplete, if execution traces are unavailable, or if the safety
oracle cannot establish deny-before-side-effect.

## Offline checkpoint and verdict

Offline checks are limited to JSON parsing, manifest identity checks, fixture
contract completeness, and the repository's existing design validators. The
protocol is `design_valid=true` but `execution_ready=false` until the
preflight supplies executable repositories, graders, and runtime bindings.

Therefore the verdict for starting the actual evaluation is **HOLD**. The
minimum next action is a separate reviewed execution-preflight artifact; do
not run a model until it reports all required bindings and an isolated oracle
check as `PASS`.
