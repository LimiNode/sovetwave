# Offline Mutation and Completeness Pilot

This is a deterministic research pilot for the question left open by the
Ponytail review: can the evaluation boundary distinguish a complete,
contract-preserving result from a plausible but incomplete one, and can it
detect controlled defects that a shorter result might hide?

The pilot is deliberately separate from the production skill, beta.2
artifacts, historical grading, and the benchmark-reliability runner. It uses
trusted structured fixtures and does not execute generated source code.

## Evidence boundary

`scripts/mutation_completeness_pilot.py` contains two small deterministic
contracts:

- an identifier-to-value mapping with a required boundary item and a stable
  rejection contract for an unknown identifier;
- a repository-root path operation that must write inside the root and block an
  outside-root path before any side effect.

The evaluator is calibrated first against five trusted fixtures:

| Fixture | Expected result | What it exercises |
|---|---|---|
| `good` | pass | all required outputs, mapping, error path, and safety boundary |
| `incomplete` | reject | missing required boundary item |
| `contract_violation` | reject | missing stable error output |
| `success_error_code` | reject | non-null error code on a successful result |
| `unsafe` | reject | outside-root side effect is allowed |

The fixture functions are repository code, not model-generated code. A future
grader must not replace them with arbitrary generated programs without a
separate isolation contract.

## Mutation status

The pilot reports five distinct outcomes:

- `killed` — the evaluator rejects the mutated trusted fixture for its declared target axis;
- `survived` — the evaluator accepts a contract-violating mutation, or rejects it for an unrelated axis;
- `invalid_mutant` — the operator did not produce a distinct valid fixture;
- `not_executed` — the mutation requires an isolation boundary that is not
  established.

`tolerated` is reserved for a contract-permitted, semantically equivalent
change and is not a coverage failure. A surviving mutation may either pass the
evaluator despite violating the contract or be rejected for an unrelated axis;
the target-axis check keeps those cases distinct from a genuine kill.

The self-test covers a missing boundary check, wrong error handling, incorrect
identifier mapping, removal of required output, and removal of the safety
check. It also includes an allowed extra field classified as `tolerated`, a
wrong rejected-path identity that survives the current evaluator, an unrelated
rejection that does not count as a kill, a malformed fixture classified as
`invalid_mutant`, and an untrusted-code mutation classified as `not_executed`.
A surviving mutation is a finding about evaluator coverage, not a pass for the
experiment; no generated code is run in the grader process.

## Completeness dimensions

The report keeps correctness dimensions separate from size:

- required task outputs and boundary cases;
- public/interface contract preservation;
- negative scenarios and error handling;
- security checks before side effects;
- fixture-provided `loc` and independent-invariant counts.

`loc` is reported as a descriptive metric only. It cannot make an incomplete
or unsafe candidate pass. Independent-invariant counts are fixture metadata in
this offline pilot; extracting them from an agent patch requires a separate,
trusted analysis boundary. A defect is reflected only in the dimensions it
violates: for example, identifier mapping makes functional completeness false,
while a wrong error path affects the negative/error-handling dimensions.

The term `mutation killed` means that this evaluator rejected a changed
trusted fixture. It is not evidence of full source-code mutation testing.

The `unobserved-wrong-rejection-path` case records the current evaluator gap
between the declared unsafe input and the path named in the rejection. It is a
real surviving contract violation, unlike the tolerated extra field.

## Planned three-arm comparison

The script emits a manifest, but does not run model evaluations. The future
comparison has three arms under one frozen task contract:

1. baseline coding agent;
2. Sovetwave frozen reference;
3. Sovetwave with an experimental explicit minimal-solution ladder.

Model, tool permissions, and environment must be fixed identically before any
run. The pilot makes no claim that the ladder improves completeness or code
economy until all three arms have comparable results and mutation-kill checks.

## Verification

Run the bounded self-test:

```text
python scripts/mutation_completeness_pilot.py --selftest
```

Expected output:

```text
Mutation/completeness pilot self-test: PASS
```

No Codex Security scan, DCG integration, model/API evaluation, or Bonsai run
is part of this PR. Those remain separate follow-up scopes.
