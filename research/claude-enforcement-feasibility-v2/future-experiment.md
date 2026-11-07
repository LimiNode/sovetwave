# Future Claude enforcement experiment

This is a plan, not an execution record. No Claude process, provider request,
hook installation, or network experiment was run for this design-only PR.

## Pinned setup

Use a disposable directory outside the repository and record:

- exact Claude Code version and binary SHA-256;
- OS, shell, Python/interpreter used by the hook, and working directory;
- settings source (`managed`, `user`, `project`, `local`) and trust result;
- hook configuration bytes and SHA-256;
- tool route, input, `tool_use_id`, hook lifecycle events, and final result;
- a side-effect counter or marker whose initial and final state are sealed.

The first target should be the documented release that supports
`onFailure: "block"`; run `2.1.120` only as a compatibility control. If the
required binary is unavailable, stop with `NOT_ASSESSABLE`.

## Fixture matrix

Run each row against the same disposable side-effect target. The no-hook row
is a control, not a policy result.

| Case | Hook condition | Expected evidence to preserve |
|---|---|---|
| no-hook control | No matching hook | Tool starts and marker changes, or the host's explicit result |
| explicit deny | Valid JSON `permissionDecision=deny` | Hook event before tool result; marker unchanged |
| explicit allow | Valid allow response | Tool result and marker change |
| non-zero exit | Exit `1`, then documented blocking exit status | Separate lifecycle events and marker state for each status |
| malformed response | Invalid JSON / invalid schema | Parser disposition and marker state |
| timeout | Hook exceeds configured timeout | Timeout event, duration, and marker state |
| launch failure | Missing interpreter or non-executable command | Launch error and marker state |
| absent hook | Remove matching hook after configuration is known | Effective settings and marker state |
| precedence | Trusted user/managed deny plus project allow/replacement | Effective source, trust result, and whether deny survives |
| route coverage | `Bash`, `Read`, `Write`, `Edit`, one MCP method | Per-route request/result correlation and marker state |
| bypass candidate | A documented non-`PreToolUse` path | Whether a protected side effect is reachable without the hook |

Use a separate fixture per row or reset the fixture and record its initial
state. Never treat a missing marker as sufficient if the tool result is not
correlated with the attempted operation.

## Trace requirements

The evidence bundle must contain raw, immutable records rather than only a
summary:

1. host invocation and version output;
2. effective settings and trust decision (with secrets and user paths
   redacted in the committed copy);
3. hook stdin, stdout, stderr, exit status, timeout, and lifecycle events;
4. host tool-use and tool-result events with `tool_use_id`;
5. fixture state before and after the attempted side effect;
6. a manifest and SHA-256 for every raw file.

If Claude does not expose the `tool_use_id -> tool_result` stream, classify
that row `NOT_ASSESSABLE` for an evidence-grade enforcement claim. Do not
reconstruct the missing edge from the assistant's final text.

## Decision criteria

### GO for a named host/route adapter

All of the following are observed on the same pinned version and fixture:

- the hook runs before the side effect;
- explicit deny prevents the side effect;
- a complete request/result correlation exists;
- success, failure, timeout, malformed output, launch failure, and absent-hook
  dispositions are observed;
- a repository cannot weaken the trusted policy, or that limitation is
  explicitly outside the claimed scope; and
- the fixture is reproducible without a model/API call, or the result is
  labelled a live-host observation rather than an offline proof.

### HOLD

Use `HOLD` when a relevant failure mode proceeds, policy authority is
uncertain, route coverage is incomplete for the intended claim, or the host
version does not support the required failure policy.

### NOT_ASSESSABLE

Use `NOT_ASSESSABLE` when the required binary, raw trace, tool-result
correlation, or control case is unavailable. This is an evidence boundary, not
a claim that the host is safe or unsafe.

## Stop rule

Do not add a production adapter, a universal shell parser, or another model
benchmark until the above matrix yields a decision for a named host and route.
If Claude remains partial or contract-dependent, keep enforcement outside the
host and retain the current offline mock as a test double only.
