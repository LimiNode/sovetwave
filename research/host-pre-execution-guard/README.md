# Host Pre-Execution Guard Pilot

This is a small offline host-boundary pilot. It demonstrates a typed admission
decision before a mock side effect; it is not a shell-command parser, a host
hook, or a sandbox for model-generated code.

The operation contract records:

- `action_id`;
- `tool_identity`;
- `action_category`;
- `target` and `scope`;
- `trust_origin`;
- `policy_context`;
- optional approval identity.

The host accepts only the closed action-category set `read`, `write`,
`external`, and `destructive`. Unknown categories are denied. A `read` is
admitted only for `system` or `user` origin; `write` and `external` require a
host-issued approval; and `destructive` is always denied. Host policy states
`unavailable` and `error` stop admission before evaluator output is trusted.

The evaluator returns one of `ALLOW`, `ASK`, `DENY`, `UNAVAILABLE`, or `ERROR`.
The host independently validates the result type, request identity, digest, and
accepted `POLICY_REVISION`; malformed or mismatched results become controlled
`ERROR` outcomes. Only a host-validated `ALLOW` reaches the in-memory mock side
effect. `ASK` requires a host-issued approval bound to the exact request
digest. `DENY`, `UNAVAILABLE`, `ERROR`, and an unconfirmed `ASK` leave the
side-effect counter unchanged.

The pilot enforces these boundaries:

- destructive operations are denied before admission;
- repository policy cannot disable the deny rule;
- evaluator failure and policy unavailability are fail-closed;
- approvals are issued by a separate host-owned in-memory authority and cannot
  be minted through the agent-facing `GuardedHostMock.admit()` interface;
- approvals cannot be forged, reused, or applied to a changed target or
  another action;
- host-issued approvals are consumed atomically at the admission boundary;
- `policy_context` is snapshotted as an immutable, acyclic JSON-compatible
  value tree; unsupported values are rejected when `OperationRequest` is
  constructed;
- every decision carries the request digest, policy revision, reason, and
  evaluator provenance.

The tests use only an in-memory counter. They do not invoke shell commands,
filesystem mutations, network operations, generated code, model APIs, or
Bonsai. `Host Pre-Execution Guard Pilot` therefore proves the mock admission
invariant only. It does not claim that Codex CLI, Claude Code, or another host
currently provides an equivalent interception hook.

## Decision matrix

| Operation | Policy result | Side effect |
| --- | --- | --- |
| trusted non-destructive read | `ALLOW` | admitted |
| untrusted read or unknown category | `DENY` | never admitted |
| write/external action without trusted approval | `ASK` | blocked until confirmation |
| destructive action | `DENY` | never admitted |
| policy unavailable | `UNAVAILABLE` | never admitted |
| evaluator failure | `ERROR` | never admitted |
| malformed or mismatched evaluator result | `ERROR` | never admitted |
| approved exact write/external action | `ALLOW` | admitted once, then approval is consumed |

The trusted setup holds `HostApprovalAuthority` separately and passes only the
resulting `Approval` to `GuardedHostMock.admit()`. Request construction rejects
non-JSON values, cycles, and non-finite numbers; this is distinct from a
runtime policy `ERROR`.

Run the deterministic pilot without model calls:

```text
python research/host-pre-execution-guard/guard.py
python tests/behavioral/test_host_pre_execution_guard.py
```

This is an independent Draft PR. It does not copy code or binaries from
Destructive Command Guard and does not modify the production skill, beta.2
artifacts, or historical benchmark results.
