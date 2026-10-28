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

`tool_events` is a bounded, redacted trace. The runner keeps lifecycle events,
call identifiers, tool names, permission outcome when exposed, exit status,
relative artifact identity, and a digest plus short preview for textual result
fields. Absolute workspace paths and unbounded command/result bodies are not
retained. The review bundle applies a second allow-list and event-count bound.

The offline pilot emits independent fields:

`agent_claimed`, `tool_invoked`, `tool_completed`, `permission_status`,
`process_status`, `artifact_identity`, `artifact_verified`, and
`assertion_status`.

An agent's text claim is never evidence of an action. `assertion_status` is
`passed` only when a matching invocation exists, a matching completion reports
`status=completed` and `exit_code=0`, and the expected artifact digest matches.
Missing trajectory is `not_assessable`; a failed tool or digest mismatch is
`failed`.

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
