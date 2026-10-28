# Benchmark reliability pilot

This draft implements the narrow reliability pass selected after reviewing
Ponytail at revision `09c434ab73ca43761c5d8b0c5d341926c2fba710`. It is an
offline pilot only. It does not change historical beta.2 grading, run model
evaluations, or make semantic claims about an agent response.

## Adopted mechanisms

| Ponytail mechanism | Sovetwave equivalent | Gap | Decision |
|---|---|---|---|
| Good/bad deterministic self-test (`benchmarks/agentic/README.md:79-80`) | Repository validators and behavioral harness tests | No evidence scorer gate | Adapted in `benchmark_reliability_pilot.py` |
| Per-call tool trajectory | Tool count and reference trace in `run_model_evals.py` | Lifecycle, completion, exit, permission, and bounded result identity were missing | Adopted as bounded `tool_events` |
| Execution-fixture scoring | Repository-grounded fixtures (`evals/behavioral/README.md:305-309`) | No deterministic artifact assertion | Adopted as an offline fixture pilot |
| Checkpoint and resume (`evals/behavioral/README.md:235-240`) | `run_model_evals.py` checkpoint/resume | No material gap for this pass | Already covered |
| Arm and revision isolation | Existing runner workspaces and provenance | Pilot does not replace the existing isolation contract | Already covered |
| Completeness separate from LOC (`benchmarks/agentic/complete.py:60-105`) | No LOC-based agentic benchmark in this harness | Different measurement boundary | Research only |
| Mutation testing | No mutation pilot | Useful offline validation | Deferred |
| LLM judge self-test | Semantic grading contract | No local judge calibration in the harness | Research only |
| Global levels, hooks, and shortcut ledger | No corresponding Sovetwave product boundary | Different scope | Rejected for this pass |

## Evidence contract

`tool_events` is a bounded, redacted trace. The runner keeps provider-native
event name, canonical lifecycle, call identifiers, tool names, permission
outcome when exposed, exit status, relative artifact identity, and a digest
plus byte count for textual result fields. Arbitrary result previews are not
retained. Absolute workspace paths are marked unavailable rather than reduced
to a basename. Each trace carries `tool_events_status`: `complete`,
`incomplete`, `truncated`, `unavailable`, or `parse_error`. `complete` is
reserved for a syntactically valid, untruncated provider stream with its
provider-specific terminal marker (`turn.completed` for Codex or `result` for
Claude), with no unclosed tool lifecycle. A syntactically valid stream without
that marker or with an unclosed lifecycle is `incomplete`.
The review bundle applies a second allow-list and event-count bound.

The normalized event contract is deliberately small:

```text
event          = invoked | completed | updated | unknown
provider_event = provider-native lifecycle name
call_id        = stable provider identifier, or null
tool_name      = provider tool/type when exposed
permission     = allowed | denied | not_available
status         = provider completion status when exposed
exit_code      = integer when exposed
path_status    = known_relative | unavailable
```

The scorer consumes only canonical `event` values and uses physical JSONL line
order as the lifecycle order. An optional provider `sequence` is validated as
a positive, strictly increasing consistency check; it never overrides line
order. A malformed, duplicate, partial, or contradictory sequence makes the
trajectory not assessable. A Claude `tool_result` without an explicit exit
code remains a completion record, not proof of a successful shell process.

The offline pilot emits independent fields:

`agent_claimed`, `tool_invoked`, `tool_completed`, `permission_status`,
`process_status`, `artifact_identity`, `artifact_verified`, and
`assertion_status`.

An agent's text claim is never evidence of an action. `assertion_status` is
`passed` only when a matching invocation and completion have one unambiguous
non-empty `call_id`, the completion follows the invocation, reports
`status=completed` and `exit_code=0`, includes artifact provenance, and the
expected artifact digest matches. A pre-existing matching file is not enough.
Missing or truncated trajectory is `not_assessable`; a failed tool or digest
mismatch is `failed`.

## Offline checks

```text
python scripts/benchmark_reliability_pilot.py --selftest
python scripts/benchmark_reliability_pilot.py \
  --task <task.json> --events <events.jsonl> \
  --workspace <workspace> --output <result.json>
```

The checked-in fixture contains one good run and one run whose agent claims
success although the tool exits with status 1. The self-test must accept the
good fixture and reject the bad fixture without contacting a model or API.

This pilot is evidence about the scorer's separation of claims and observed
execution. It is not a replacement for provider-native traces, a semantic
grader, or a production acceptance gate.
