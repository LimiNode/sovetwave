# Repository-grounded experiment fixtures

This is a small offline fixture set for the next coding-agent comparison. It
binds the experiment design to existing repository paths without running model
output or generated source code.

The three contracts are:

1. `contract-coding-task.json` — a `scripts/build_bundle.py::sanitize_result`
   result with a complete and an incomplete candidate;
2. `reuse-helper-task.json` — import and reuse of the existing module-level
   `eval_schema.validate_applicable_axes` helper versus a new local validator;
3. `security-negative-task.json` — a traversal-like fixture path rejected
   before any side effect, grounded in the fixture-root boundary in
   `scripts/run_model_evals.py`.

Every task is pinned to repository revision
`cdbd2827e0f440f171edddefc3e3556a74e5d7a5` and to SHA-256 of each referenced
source file. A marker proves only that the named source text exists at that
revision. The reuse check additionally imports the established module-level
helper and probes its existing contract with trusted synthetic inputs.

The graders classify trusted structured candidate records. They do not import
or execute generated code and do not establish that a coding agent actually
implemented, invoked, or preserved the referenced path. In particular,
`side_effects=[]` in the security case is fixture data, not an observed
filesystem trace; `grade_security()` is not a host guard. A future experiment
needs a separately reviewed executable oracle and isolation boundary before it
can claim behavioural correctness or execution readiness.

Run the deterministic checks with:

```text
python scripts/validate_experiment_fixtures.py --selftest
python -m pytest -q tests/behavioral/test_experiment_fixtures.py
```
