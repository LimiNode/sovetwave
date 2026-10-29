# Repository-grounded experiment fixtures

This is a small offline fixture set for the next coding-agent comparison. It
binds the experiment design to existing repository paths without running model
output or generated source code.

The three contracts are:

1. `contract-coding-task.json` — a `scripts/build_bundle.py::sanitize_result`
   result with a complete and an incomplete candidate;
2. `reuse-helper-task.json` — reuse of the existing
   `safe_reference_path` helper in `scripts/run_model_evals.py` versus a new
   local parser;
3. `security-negative-task.json` — a traversal-like fixture path rejected
   before any side effect, grounded in the fixture-root boundary in
   `scripts/run_model_evals.py`.

The grader consumes only structured candidate records from these JSON files and
checks the referenced source markers. It does not import or execute generated
code. A future experiment manifest may bind these fixtures after a separate
review; adding them here does not make a runtime or model experiment ready.

Run the deterministic checks with:

```text
python scripts/validate_experiment_fixtures.py --selftest
python -m pytest -q tests/behavioral/test_experiment_fixtures.py
```
