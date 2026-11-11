# Offline validation record

Historical release: `437c8ff116a96c69753bb7db40779d86fd892e00`.
Combined candidate: `394ca374b20e9b40b285d05492fa9a317ec86463`, skill-tree
hash `62aad1981520d72be6e7266d94bb2be3a9c9d646edced0cd5df24a3b692e6324`.

Checks run without model or host calls:

- `manifest.json` and six fixture contracts parsed and joined: PASS;
- six task IDs, six fixture IDs, 60-call ceiling, and `HOLD` verdict: PASS;
- combined candidate `394ca374b20e9b40b285d05492fa9a317ec86463` validated in its
  integration worktree: `33 suites / 297 cases`;
- `git diff --check`: PASS;
- `python evals/validate_evals.py`: `33 suites / 281 cases`;
- `python .github/scripts/validate_skill.py skills/sovetwave`: PASS;
- `python scripts/validate_experiment_readiness.py --selftest`: design valid,
  execution blocked;
- `python -m pytest -q tests/behavioral/test_experiment_readiness.py tests/behavioral/test_experiment_fixtures.py`:
  `23 passed, 17 subtests passed`;
- `python -m json.tool research/beta3-practical-effectiveness/manifest.json`:
  PASS.
- exact-head CI for the combined candidate: 3/3 success;
- exact-head CI for this research PR: 3/3 success.

These checks establish only the offline protocol and contract integrity. They
do not establish that a model, host, generated program, or execution oracle
has run successfully.
