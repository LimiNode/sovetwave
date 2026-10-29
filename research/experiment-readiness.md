# Experiment Readiness — three-arm completeness comparison

This note prepares a reproducible dry-run for a later comparison of coding
agent behaviour. It does not execute a model, call an API, contact Bonsai, or
change the production Sovetwave skill.

The checked-in manifest is
[`experiment-readiness-manifest.json`](experiment-readiness-manifest.json).
The research-only treatment for the third arm is
[`experiment-readiness-minimal-ladder.md`](experiment-readiness-minimal-ladder.md).

## Arms and exact identity

The harness revision is `cdbd2827e0f440f171edddefc3e3556a74e5d7a5`. The frozen
production reference is beta.2 at
`efb48ec0b10dfbc8b6ca198b5c1b3b09f49be820`.

The frozen skill tree hash is calculated over every file below
`skills/sovetwave/`, in sorted path order, by concatenating
`path UTF-8 + NUL + file bytes + NUL` and taking SHA-256. The recorded value is:

```text
abb94a0860de21f326e204a126e699f60f1e9739d4a906902e9e6d87b0367eb5
```

The three arms are:

1. baseline — no Sovetwave skill;
2. sovetwave-frozen — the beta.2 skill tree at the pinned revision;
3. sovetwave-explicit-ladder — the same frozen tree plus the separately hashed
   research overlay.

The overlay is not installed into `skills/sovetwave/` and is not a production
change.

## Shared task contract

All arms must receive the same four tasks and expected outputs from the
manifest:

- necessity and repository-reuse ordering;
- a complete interface path with invalid-input and dependency-failure cases;
- untrusted-input validation before a side effect;
- a short-stub negative control where the happy path is insufficient.

Each task has explicit negative controls. Correctness, completeness, and
security gates are evaluated independently. Cost and size are measured only
after those gates pass; a shorter answer cannot win by omitting required work.

## Runtime bindings still required

The dry-run intentionally leaves `model_id`, host endpoint, tool surface,
permission profile, and environment snapshot null. Before execution they must
be bound to the same values for all three arms and recorded in a new immutable
run manifest. A missing binding is `not_executed`, not a failed or successful
observation.

Activation evidence must come from the host/tool trace. A final response is
not proof that a skill or overlay was loaded. Missing activation trace is
`unavailable`.

## Allocation and stopping rules

The proposed allocation is three repetitions per arm, four tasks per
repetition, with seeded block randomization (`20261029`) and at most 36 model
calls. Stop before comparison if task contract, model, host, permissions, or
environment differ; if required traces or artifact provenance are missing; or
if a security gate cannot establish deny-before-side-effect.

Paired claims require matching arm, task, repetition, and runtime identity.
Malformed artifacts are `invalid`; untrusted generated code without a reviewed
isolation boundary is `not_executed`.

## Dry-run verification

Run:

```text
python scripts/validate_experiment_readiness.py --selftest
python -m pytest -q tests/behavioral/test_experiment_readiness.py
```

These checks validate hashes, arm identity, task-contract consistency,
allocation arithmetic, and the explicit no-model-call boundary. They do not
claim that the comparison has been run.
