# Claude trust boundaries and configuration authority

This note is part of the Claude enforcement feasibility spike. It describes
the boundary that a future adapter would have to protect; it does not claim
that the boundary is currently enforced.

## Actors and configuration layers

The official Claude documentation describes settings and permissions that may
come from managed, user, project, local, and command-line sources. The same
source order does not apply to every kind of decision: scalar settings, list
merging, permission rules, hook decisions, and mods have separate semantics.
A future fixture must record the source of every active setting and the host's
decision about trust.

| Boundary | Required property | Current evidence | Status |
|---|---|---|---|
| Settings source -> effective scalar setting | A lower-trust project value cannot silently replace a higher-trust managed value | Published settings contract reviewed; no local fixture | `documented`, version applicability unconfirmed |
| Permission rules -> effective permission | A matching deny remains blocking even when an allow is more specific | Published permissions contract reviewed; no local fixture | `documented`, version applicability unconfirmed |
| Trust review -> project hooks | Loading a project hook is an explicit, reviewable trust decision | The preserved setup loaded a disposable project configuration; trust precedence is not sealed | `artifact-verified` setup, enforcement `not_assessable` |
| Hook decision -> tool dispatch | A blocking hook decision is applied before the side effect and cannot be relabelled as an allow | One Bash marker was absent after an explicit deny | `locally-observed`, route-bounded |
| Hook failure -> tool dispatch | Failure, timeout, malformed output, or launch failure must have a known disposition | Exit 1, malformed output, and timeout allowed markers in the preserved matrix; launch failure not run | `contract-dependent` / `not_assessable` |
| Mod -> permission/hook outcome | An installed mod cannot override the protected outcome in the claimed trust mode | No mod fixture; installed version applicability unconfirmed | `not_assessable` |
| Non-tool path -> side effect | Actions outside `PreToolUse` cannot bypass mandatory policy | No route-complete trace or bypass inventory exists | `not_assessable` |

## Settings precedence (a configuration decision)

The current settings reference documents this order for the same scalar key,
highest first: managed settings, command-line `--settings`, project-local
settings, shared project settings, and user settings. A command-line value is
per-session; managed settings are not overridden by repository or user files.
Environment variables are not one more level: precedence is decided per key.
Some security-sensitive keys have stricter exceptions, so the generic stack
must not be used as a substitute for the key-specific contract.

This is a statement about choosing an effective setting. It is not a statement
that a project file can override a permission `deny`, nor that every hook source
can disable a managed hook.

## Permission deny precedence (an authorization decision)

The permissions reference separately documents that a matching `deny` blocks a
call even when a narrower `allow` matches it. The same deny-first rule applies
between `ask` and `allow`, and permission rules are enforced by Claude Code,
not by the model. This is stronger than the scalar settings stack for the
specific permission decision, but it does not establish hook-failure
semantics.

## Hook decision precedence (a dispatch decision)

The hooks reference documents that a blocking hook (including exit code `2` or
an explicit blocking decision) takes precedence over an allow rule, and that
exit code `2` stops the tool call before permission rules are evaluated. The
permissions reference also documents the converse boundary: a matching
permission `deny` remains blocking when a hook returns `allow` or `ask`.

Thus the following are separate facts, not one universal ordering:

1. permission `deny` cannot be carved out by a more specific allow;
2. a blocking `PreToolUse` hook can stop a call before the permission check;
3. a hook `allow` cannot grant a call that the permission layer denies; and
4. none of these facts says what happens when the hook is absent or fails,
   unless the pinned version and `onFailure` policy establish it.

## Managed policy and managed hooks

Managed settings are the highest settings tier in the published contract. The
hooks reference further documents `allowManagedHooksOnly`: when managed
settings enable it, user, project, local, and plugin hooks are blocked, while
managed hooks remain available. It also states that hooks from different
settings levels merge rather than replacing managed hooks, and that
`disableAllHooks` outside the managed tier cannot disable managed hooks.

These are documented host controls, not local Sovetwave evidence. Their
applicability to Claude Code `2.1.120` remains unconfirmed. A production
claim must identify whether the required managed policy is actually deployed
and which managed source supplied it.

## Mods are a separate authority layer

The permissions reference documents that a plugin mod handling `tool.check`
runs after `PreToolUse`. With managed settings or a Team/Enterprise login,
the documented outcomes preserve a matching deny and a hook block by default.
Without those managed/team conditions, the mod can approve a call that a
permission deny or a `PreToolUse` hook blocked. The same page identifies this
mod surface as requiring Claude Code `2.1.292` or later.

Consequently, a hook-only test cannot establish enforcement in an environment
where mods may be installed. A future experiment must either prohibit mods as
part of the trusted deployment boundary or test their exact precedence on the
pinned version. The preserved `2.1.120` run did neither.

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
6. An installed mod approves a call after a hook or permission decision and
   changes the effective outcome.

The first three threats are not solved by a prompt instruction. The fourth is
not solved by adding more shell patterns to a hook. The fifth is controlled by
pinning the binary and preserving its hash. The sixth requires a separate
authority and trust test; it cannot be inferred from a successful hook deny.

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
- scalar setting precedence versus permission deny precedence;
- hook block versus permission allow, and hook allow versus permission deny;
- managed `allowManagedHooksOnly` and `disableAllHooks` controls;
- mod absent, mod approving, and mod attempting to override a hook/deny;
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
