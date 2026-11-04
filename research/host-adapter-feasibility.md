# Host Adapter Feasibility

Status: `draft` research note  
Revision under review: `3fa30fd377dfae8eca8a47fe98548b159128e8e1`  
Audit date: `2026-11-02`

## Decision boundary

PR #64 proves a typed admission decision before an in-memory mock side effect.
It does not prove that Codex CLI, Claude Code, or another host dispatches every
relevant tool call through an equivalent boundary. This note records the
smallest next investigation. It does not add a host adapter, a shell parser,
or a production-skill rule.

The target claim is deliberately narrow:

> For one named host and one named tool route, a host-supported hook receives
> the operation before the side effect and a `DENY` (or equivalent) prevents
> that side effect.

Anything broader requires separate route-by-route evidence.

## Evidence classification

The official pages below are living documentation. They were retrieved on
`2026-11-02`; neither page pins the complete contract to the local binary
version. A statement marked `documented` therefore describes the current
published contract, not automatic compatibility with an older or prerelease
binary. A statement marked `local observation` came from the installed CLI;
`not tested` means that no hook was executed, and `unavailable` means that the
source does not establish the requested property.

Official sources:

- [Codex Hooks](https://learn.chatgpt.com/docs/hooks) — current Codex hook
  configuration, input/output, trust review, coverage, and failure notes.
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks) —
  current Claude Code hook events, schemas, decisions, exit codes, and
  failure handling.

## Local CLI observations

These observations come from the installed binaries on the audit machine. They
are leads for a reproducible spike, not project-wide compatibility claims.

| Host | Version | Evidence status | Observed evidence | What remains unknown |
|---|---|---|---|---|
| Codex CLI | `0.146.0-alpha.3` | `local observation` | `codex features list` reports `hooks` as `stable` and enabled. `codex --help` exposes `--dangerously-bypass-hook-trust`; the help for stream output also exposes `--include-hook-events`. | No hook was executed. The local command output does not establish the request schema, route coverage, or failure semantics for this exact prerelease binary. `plugin_hooks` is reported as removed, so it must not be assumed to be the adapter surface. |
| Claude Code | `2.1.120` | `local observation` | `claude --help` exposes `--include-hook-events`. The installed release notes mention `PreToolUse`; the local installation has a `PreToolUse` configuration entry, but that host-local configuration is not a Sovetwave contract. | No hook was executed. In particular, the current documentation's `onFailure: "block"` requires Claude Code `2.1.295` or later; it cannot be assumed on `2.1.120`. |

The observations do not establish that either host can load
`research/host-pre-execution-guard/guard.py` directly. They also do not show
that a repository-local configuration can weaken a user-level deny rule.

## Published contract versus observed enforcement

The following matrix keeps the documentation claim separate from an execution
observation.

| Host/version | Hook and documented contract | Failure/timeout contract | Route coverage | Approval behaviour | Known limitation | Local verification |
|---|---|---|---|---|---|---|
| Codex CLI `0.146.0-alpha.3` | **Documented, version applicability unconfirmed:** current Codex docs define `PreToolUse`, input fields `tool_name`, `tool_use_id`, and `tool_input`; JSON `permissionDecision: "deny"` or exit code `2` can deny a supported call. `permissionDecision: "ask"` is documented as parsed but unsupported. | **Documented:** callback error, timeout, or malformed response can fail without blocking the tool; explicit denial is different from hook failure. Default timeout is documented for current Codex configuration, not proven for this binary. | **Documented:** Bash, `apply_patch`, MCP, and other local function tools; hosted tools are outside this path and specialized routes may opt out. | `ASK` is not a supported PreToolUse decision in the current docs. Permission approval is a separate `PermissionRequest` path. | Non-managed hooks require trust review; project-local hooks load only when the project layer is trusted. Current docs warn that tool hooks are not a complete enforcement boundary. | **Not tested.** Only CLI help and feature listing were inspected. |
| Claude Code `2.1.120` | **Documented current contract, version applicability partly unconfirmed:** current docs define `PreToolUse` before tool processing with `tool_name`, `tool_input`, and `tool_use_id`; `permissionDecision` supports allow/deny/ask/defer. Exit code `2` blocks a blockable `PreToolUse` call. | **Documented current contract:** failures are non-blocking by default; `onFailure: "block"` makes a failure block the action, but the docs require `2.1.295+`. Therefore fail-closed is **unavailable/not established** on the installed `2.1.120`. | **Documented:** built-in tools and MCP names; `EndConversation` is excluded. File mentions using `@` can bypass `PreToolUse` because no tool call occurs. | `ask`/`defer` are documented for current `PreToolUse`; exact behaviour on `2.1.120` remains untested. | Permission precedence, trust scope, and non-tool paths still require a fixture. A hook can be present without covering every side effect. | **Not tested.** CLI help and local release notes were inspected; no model or tool call was run. |

The Codex and Claude rows are not interchangeable. In both cases the
published denial mechanism is stronger than a prompt instruction, but neither
row proves the Sovetwave fail-closed invariant on the installed version.

## Candidate contract to verify

The adapter spike should test one host at a time and preserve the following
fields when the host exposes them:

- host and host-version identifier;
- tool and route identifier;
- operation input and target/scope;
- working directory and trust/configuration origin;
- a request identifier or another stable correlation value;
- hook decision and explanation;
- hook exit status, timeout, and stderr/stdout disposition;
- whether the underlying side effect started.

The decision vocabulary may be host-specific. Map it to the pilot's
`ALLOW`/`ASK`/`DENY`/`UNAVAILABLE`/`ERROR` only after the host contract is
observed; do not infer equivalence from similar words.

## Bounded offline spike

The next PR should be a research-only branch with a disposable fixture. It
must not invoke a model, make a network request, mutate a real project, or
install a third-party guard.

1. Discover the host's documented hook configuration and exact input/output
   schema at a pinned local version.
2. Install a temporary hook that writes only a structured request record to a
   temporary directory and returns a deterministic deny decision.
3. Drive the host through an offline replay or host-provided fixture surface.
   If the host has no such surface, stop and record `not assessable` instead of
   substituting a live model call.
4. Repeat for one read-only route and one side-effecting route. The latter must
   show that the side effect counter or fixture file is unchanged after deny.
5. Exercise hook failure, timeout, malformed output, and absent-hook cases.
   Record the actual host result for each case; do not assume fail-closed
   behaviour.
6. Check whether repository configuration can change the user-level deny
   outcome. If precedence is undocumented, classify it as
   `contract-dependent`.

## Acceptance and stop rules

Promote an adapter proposal only when all of the following are observed for a
named host and route:

- the hook runs before the side effect;
- a deterministic deny prevents the side effect;
- the request can be correlated with the attempted operation;
- malformed output, timeout, and hook failure have an explicitly observed
  disposition;
- user-level deny policy cannot be weakened by repository input, or the
  limitation is made explicit;
- the fixture is reproducible without a model/API call.

If any item is unavailable, keep the result as `not assessable` or
`contract-dependent` and leave PR #64's offline mock as the only implemented
guard boundary. Do not write a universal shell classifier to compensate for a
missing host contract.

## Current result

The CLI observations establish that both installations expose hook-related
surface area. They do **not** establish an executable Sovetwave adapter or
pre-execution enforcement. The next discriminating artifact is therefore a
host-specific offline fixture, not production code. Until that fixture exists,
the correct status is `investigation target`.
