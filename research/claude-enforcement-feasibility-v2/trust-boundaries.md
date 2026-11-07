# Claude trust boundaries and configuration authority

This note is part of the Claude enforcement feasibility spike. It describes
the boundary that a future adapter would have to protect; it does not claim
that the boundary is currently enforced.

## Actors and configuration layers

The official Claude documentation describes settings and permissions that may
come from managed, user, project, and local sources. Their exact precedence,
trust review, and loading behaviour are host policy, not properties that
Sovetwave may infer from a JSON file. A future fixture must record the source
of every active setting and the host's decision about trust.

| Boundary | Required property | Current evidence | Status |
|---|---|---|---|
| Managed policy -> host | A centrally controlled deny cannot be replaced by repository input | No precedence fixture in the preserved evidence | `not_assessable` |
| User policy -> project settings | A repository cannot weaken a user-level deny without an explicit trusted action | Existing local run used project settings only; user-level precedence was not tested | `not_assessable` |
| Trust review -> project hooks | Loading a project hook is an explicit, reviewable trust decision | The preserved setup loaded a disposable project configuration; trust precedence is not sealed | `artifact-verified` setup, enforcement `not_assessable` |
| Hook decision -> tool dispatch | An explicit deny is applied before the side effect | One Bash marker was absent after an explicit deny | `locally-observed`, route-bounded |
| Hook failure -> tool dispatch | Failure, timeout, malformed output, or launch failure must have a known disposition | Exit 1, malformed output, and timeout allowed markers in the preserved matrix; launch failure not run | `contract-dependent` / `not_assessable` |
| Non-tool path -> side effect | Actions outside `PreToolUse` cannot bypass mandatory policy | No route-complete trace or bypass inventory exists | `not_assessable` |

## Threat model

The relevant adversary is a repository or task that can influence project-local
configuration, hook commands, tool inputs, or the selected route. The host
user and managed configuration are trust anchors only if the host actually
enforces their authority. The following are explicit threats:

1. A project file disables, replaces, or shadows a user-level deny.
2. A project hook is accepted without a trust review, or a trust decision is
   lost when the working directory changes.
3. A hook reports failure, times out, or cannot start and the host proceeds.
4. A side effect uses a route that has no matching `PreToolUse` event.
5. A policy is written for one binary version but interpreted by another.

The first three threats are not solved by a prompt instruction. The fourth is
not solved by adding more shell patterns to a hook. The fifth is controlled by
pinning the binary and preserving its hash.

## Required authority invariant

The minimum invariant for a production claim is:

> An untrusted repository cannot weaken a trusted deny, and no covered side
> effect starts when the hook's required decision or execution is unavailable.

This invariant is currently **not established** for Claude Code. The
project-local hook observation demonstrates a mechanism, not authority over
all configuration layers.

## What must be observed next

The future fixture must use the same disposable side-effect target for paired
cases:

- managed/user deny with a project allow or replacement;
- user deny with no project settings;
- trusted project hook and untrusted project hook;
- changed working directory and nested repository;
- absent hook and hook launch failure;
- one covered tool route and one candidate bypass route.

Each case needs the effective settings source, trust prompt/result, host
version, hook lifecycle, side-effect state, and a raw correlation identifier.
If the host does not expose these fields, the corresponding claim remains
`not_assessable` rather than being inferred from the final assistant message.

## Architectural consequence

Until this authority invariant is demonstrated, a Claude-specific adapter may
be documented only as a version- and route-scoped admission helper. A strict
fail-closed policy must sit at a trusted external execution boundary that the
repository cannot rewrite.
