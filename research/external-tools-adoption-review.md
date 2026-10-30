# External Engineering Tools Adoption Review

This review compares three upstream projects with Sovetwave at the pinned
revisions below. It records transferable mechanisms, not copied prompts or
implementation code. The review is intentionally separate from beta.2,
historical benchmark artifacts, and the Draft benchmark-reliability work.

Audit date: `2026-10-29`.

## Scope and evidence

| Project | Audited revision | License evidence | Primary evidence reviewed |
|---|---|---|---|
| [OpenAI Codex Security](https://github.com/openai/codex-security/tree/11a45947c7dcd257fcc3e5755d0a7fe5af8b359b) | `11a45947c7dcd257fcc3e5755d0a7fe5af8b359b` | [Apache-2.0](https://github.com/openai/codex-security/blob/11a45947c7dcd257fcc3e5755d0a7fe5af8b359b/LICENSE) | [`docs/agent-workflows.md`](https://github.com/openai/codex-security/blob/11a45947c7dcd257fcc3e5755d0a7fe5af8b359b/docs/agent-workflows.md), security workflow skills |
| [Destructive Command Guard](https://github.com/Dicklesworthstone/destructive_command_guard/tree/deff5c075df1893b5207604755969ab20f299170) | `deff5c075df1893b5207604755969ab20f299170` | [custom MIT rider](https://github.com/Dicklesworthstone/destructive_command_guard/blob/deff5c075df1893b5207604755969ab20f299170/LICENSE); GitHub SPDX is `NOASSERTION` | [`docs/configuration.md`](https://github.com/Dicklesworthstone/destructive_command_guard/blob/deff5c075df1893b5207604755969ab20f299170/docs/configuration.md), Codex integration documentation |
| [Ponytail](https://github.com/DietrichGebert/ponytail/tree/09c434ab73ca43761c5d8b0c5d341926c2fba710) | `09c434ab73ca43761c5d8b0c5d341926c2fba710` | [MIT](https://github.com/DietrichGebert/ponytail/blob/09c434ab73ca43761c5d8b0c5d341926c2fba710/LICENSE) | [`AGENTS.md`](https://github.com/DietrichGebert/ponytail/blob/09c434ab73ca43761c5d8b0c5d341926c2fba710/AGENTS.md), [`skills/ponytail/SKILL.md`](https://github.com/DietrichGebert/ponytail/blob/09c434ab73ca43761c5d8b0c5d341926c2fba710/skills/ponytail/SKILL.md), agentic benchmark documentation |

The revisions are an audit snapshot, not a claim that any upstream project is
the sole authority for the proposed design. Upstream behavior, host APIs, and
licenses can change; any implementation PR must re-pin and re-check them.

## Adoption matrix

| Mechanism | Upstream evidence | Sovetwave equivalent | Actual gap | Decision | Smallest useful verification |
|---|---|---|---|---|---|
| Minimal-solution ladder | Ponytail `AGENTS.md` asks whether the feature is needed, whether the repository or standard library already provides it, and only then permits a new implementation. | [`code-economy.md`](../skills/sovetwave/references/code-economy.md) covers the underlying principles: establish the contract, inspect repository reuse, compare contracts before consolidating, bound the change, and verify the result. It does not state Ponytail's explicit ordered ladder (`necessity → repository reuse → stdlib/platform → existing dependency → new code`). | The semantic discipline is mostly covered, but the value of making that exact ordering explicit has not been established. | `experiment` (production adoption `not_decided`) | Compare fixed tasks with the existing Sovetwave guidance and with an experimental explicit ladder; measure completeness, unnecessary new abstractions, and validation retention. Do not infer value from LOC alone. |
| Completeness separate from code size | Ponytail's agentic benchmark reports completeness separately from LOC and tests the full result, not only a shorter patch. | Current behavioral harness has assertion-based semantic cases; the benchmark-reliability pilot is a separate Draft PR. | Historical benchmark does not yet provide a mutation-kill or completeness-vs-LOC arm. | `experiment` | Add a deterministic offline arm after benchmark-reliability is accepted; mutate one required sink and require the completeness check to fail while LOC remains unchanged. |
| Security task routing | Codex Security `docs/agent-workflows.md` separates repository scan, diff scan, triage, fix, and independent verify-fix. | [`verification-discipline.md`](../skills/sovetwave/references/verification-discipline.md) separates finding, evidence, disconfirmation, and verification; [`agent-instructions.md`](../skills/sovetwave/references/agent-instructions.md) states that prompts are not a hard security boundary. | No narrow route and fixture set explicitly covering attacker/source → controls → sink → independent fix verification. | `adapt` | First prove the case gap against current fixtures; then add a small security-review route and positive/negative cases in a separate PR. |
| External security scanner | Codex Security provides `cs scan`, `cs validate`, saved findings, coverage, threat-model artifacts, and separate fix verification. | No internal scanner is present or required. | Sovetwave cannot provide scanner coverage, provider isolation, or saved findings by prompt text. | `external_integration` | Use Codex Security or another approved scanner only when explicitly requested; record revision, scope, provider, data boundary, and coverage. Do not make every PR depend on a live or paid scan. |
| Threat model and source/control/sink tracing | Codex Security workflows require an attacker, source, controls, sink, impact, and proof gaps before a finding is accepted. | Existing trust-boundary, architecture-evidence, and verification references cover parts of this chain. | The security-specific vocabulary is not yet a compact route in Sovetwave. | `adapt` | Add one bounded fixture for a reachable untrusted-input sink and one negative control where the control blocks the path; require a counterevidence statement. |
| Pre-execution command blocking | DCG intercepts commands in host hooks before execution and separates allow, warn, ask, and deny outcomes. | Sovetwave documents host permissions, sandboxing, and tool allow/deny rules; it cannot enforce a host hook from a skill. | No repository-owned host adapter or mock contract currently proves pre-execution blocking. | `experiment` | Define an offline mock host contract first: no side effect before `deny`, explicit approval for `ask`, and a fail-closed hook error. Do not implement a universal shell parser. |
| Repository configuration trust | DCG accepts only monotonic enforcement settings from automatically discovered project config; a project cannot weaken user policy. | Sovetwave treats repository artifacts as data by default and has explicit trust-boundary cases. | The same invariant is not tested at a host pre-execution boundary. | `adapt` | Add a negative mock-host case where repository config attempts to disable a deny rule; the decision must remain denied. |
| False-positive control | DCG tests commands that mention a dangerous string without executing it and maintains dialect/context-specific corpora. | Tool-use and verification cases distinguish command status and evidence, but no command-policy parser exists in Sovetwave. | Copying a regex command parser would create a second security engine with an unknown contract. | `reject` as an internal implementation; `experiment` as host-contract testing | Test the host integration boundary with safe prose and quoted data, not a new shell parser. Delegate command classification to the selected guard. |
| DCG source, binary, or dependency | DCG's `LICENSE` is titled `MIT License (with OpenAI/Anthropic Rider)` and removes rights for restricted parties, including use, benchmarking, and derivative works. | None. | The rider is incompatible with treating DCG code as an ordinary Sovetwave dependency without legal review. | `reject` | No code, binary, vendored corpus, or derived implementation from DCG. Re-check license applicability before any external deployment decision. |

## Decisions by project

### Ponytail

The minimal-solution questions are useful as a method. Sovetwave's independently
formulated `code-economy.md` already covers the main principles—an observable
contract, repository reuse, contract-aware consolidation, bounded semantic
surface, and explicit verification—but it does not state Ponytail's exact
ordered ladder. That difference is a hypothesis about decision quality, not a
demonstrated production gap. Keep production adoption `not_decided` until a
separate fixed-task experiment compares the existing guidance with an explicit
ladder and measures completeness, unnecessary abstractions, and retained
validation. Do not add Ponytail levels, plugin hooks, or an upstream dependency
in this review.

Ponytail's `AGENTS.md` and `skills/ponytail/SKILL.md` can be used as standalone
instruction text without installing the full plugin. The plugin adds host
integration and auxiliary commands; it is a different distribution boundary.
Its MIT license permits adaptation when the license and notice conditions are
preserved. This review adapts the underlying decision hypothesis and does not
copy Ponytail's prompt text.

### Codex Security

The transferable part is the workflow boundary, not a second scanner inside the
skill. A security task should state its scope and threat model, distinguish scan
from triage and fix, and verify the original path independently after a change.
The CLI remains an optional external tool. It may require authentication,
provider-side processing, and paid model calls; private-source handling must be
explicit. No automatic scan is added to the normal Sovetwave PR gate here.

### Destructive Command Guard

The architectural lesson is stronger than a warning in a prompt: dangerous
operations need a host/tool boundary that can deny before execution. The
repository configuration must not weaken a user's protection, and hook failure
must not silently become permission to run. That contract can be tested with a
small offline mock, but DCG's implementation, binary, and license rider are
not adopted.

## Proposed sequence of bounded follow-ups

These are proposals, not changes made by this review:

1. Finish and review benchmark reliability PR #58 independently.
2. Run a deterministic minimal-solution/completeness experiment arm without
   changing the production skill.
3. If a fixture gap is demonstrated, add a small security-review evidence case
   set with source/control/sink and independent verify-fix assertions.
4. Define a host pre-execution safety contract and offline mock, including
   deny-before-side-effect, fail-closed hook errors, explicit approval, and
   repository-policy non-weakening.
5. Consider an external Codex Security scan only as an explicitly authorized
   development operation; preserve its scope, provider, revision, and coverage.

No step above authorizes a model/API/Bonsai evaluation, a beta.3 release, a
production skill rewrite, or a merge.

## Limitations

- This is a static source and license audit at the pinned revisions; it is not
  a runtime demonstration of Codex Security or DCG.
- A security scanner's no-finding result would not establish complete coverage.
- A host guard covers only the execution paths that actually dispatch through
  its hook; tool surfaces outside that boundary remain a separate question.
- The DCG rider is recorded as a license restriction, not legal advice.
- The proposed negative cases are acceptance criteria for later PRs, not results
  claimed by this documentation-only change.
