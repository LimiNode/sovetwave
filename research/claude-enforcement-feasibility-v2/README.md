# Claude-specific enforcement feasibility v2

Status: `draft` / research-only

Audit date: `2026-11-07`

Base revision: `293151a5543e99a8b8eb2969bf666f583fb261e6`

## Decision

`HOLD` for a production Claude-specific adapter.

`NOT_ASSESSABLE` for the stronger claim that Claude Code provides a
fail-closed boundary when the hook itself fails. The published contract and
the preserved local evidence establish a narrower result: a trusted,
version-specific `PreToolUse` hook can act as a partial admission boundary
when it returns an explicit denial. They do not establish universal tool
coverage, failure-closed behaviour on the installed `2.1.120`, or protection
against policy weakening by repository configuration.

This is a design-only investigation. It does not install hooks, run Claude or
Bonsai, make a provider request, modify the historical evidence bundle, or add
a production adapter.

## Evidence classes

Every claim in this directory uses one of these labels:

- `documented`: stated by the current official Claude Code documentation;
- `version-applicability-unconfirmed`: documented for the current product
  reference, but not established for the installed `2.1.120`;
- `artifact-verified`: the committed evidence summary or hash was checked;
- `locally-observed`: reported by the preserved local run for one host, route,
  and fixture;
- `agent-reported`: retained from the earlier run, with no sealed raw stream;
- `not_assessable`: the required trace, route, version, or control is absent.

The labels are not interchangeable. In particular, an artifact-verified
summary is not a replacement for a raw `tool_use_id -> tool_result` stream.

## Sources and scope

Normative sources reviewed for this design:

- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Claude Code permissions](https://code.claude.com/docs/en/permissions)

These are living pages. Their current text is a published contract, not proof
of compatibility with every installed binary. The existing repository note
`research/host-adapter-feasibility.md` records the review date and the
version-applicability warning. No network execution or host experiment was
performed for this PR.

The preserved local record is
[`research/host-hook-evidence/`](../host-hook-evidence/README.md): Claude Code
`2.1.120`, Windows 11, the `Bash` route, disposable project settings, and a
local provider. Its source bundles and SHA-256 values remain outside this PR;
the committed summaries are not rewritten.

## What is established

| Question | Result | Boundary |
|---|---|---|
| Can an explicit `PreToolUse` denial stop a side effect? | `locally-observed` for one `Bash` fixture | The sealed hook record and marker result exist, but the complete Claude stream does not. |
| Does hook failure fail closed on `2.1.120`? | `not_assessable` as a product guarantee; the preserved matrix observed marker creation for exit `1`, malformed output, and timeout | One version, one route, one configuration; no universal claim. |
| Does `onFailure: "block"` settle the question? | `version-applicability-unconfirmed` | The current reference requires a newer Claude Code version than `2.1.120`; the newer binary was not run. |
| Can a repository weaken a user-level deny? | `not_assessable` | User/project/managed precedence and trust controls need a dedicated fixture. |
| Are all side-effect routes covered? | `not_assessable` | Only `Bash` was observed; `Read`, `Write`, `Edit`, MCP, and non-tool paths were not run. |

The correct architecture is therefore a partial host admission boundary plus a
trusted external execution boundary for any policy that must remain fail
closed. Prompt discipline, a project-local hook, or the offline mock in
`research/host-pre-execution-guard/` is not that external boundary.

## Required invariant for a future adapter

For a named Claude Code version and named route, a future adapter may claim
`GO` only if it demonstrates, with a preserved raw trace, that:

1. the hook ran before the side effect;
2. an explicit deterministic denial prevented the side effect;
3. the request and result correlate through `tool_use_id` (or an equivalent
   host identifier);
4. hook failure, timeout, malformed output, launch failure, and absent-hook
   cases have observed dispositions;
5. trusted and untrusted configuration precedence is either proven or stated
   as a limitation; and
6. the result is reproducible without a model call, or the experiment is
   explicitly scoped as a live-host test rather than an offline proof.

Missing one of these observations keeps the result `HOLD` or
`NOT_ASSESSABLE`; it does not justify a universal shell classifier.

The supporting contract matrix, trust-boundary analysis, route coverage, and
future experiment plan are kept in the companion files in this directory.
