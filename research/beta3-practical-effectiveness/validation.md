# Offline validation record

Revision under review: `437c8ff116a96c69753bb7db40779d86fd892e00` plus the
research-only files in this directory.

Checks run without model or host calls:

- `manifest.json` and six fixture contracts parsed and joined: PASS;
- six task IDs, six fixture IDs, 60-call ceiling, and `HOLD` verdict: PASS;
- `git diff --check`: PASS;
- `python evals/validate_evals.py`: `33 suites / 281 cases`;
- `python .github/scripts/validate_skill.py skills/sovetwave`: PASS;
- `python scripts/validate_experiment_readiness.py --selftest`: design valid,
  execution blocked;
- `python -m pytest -q tests/behavioral/test_experiment_readiness.py tests/behavioral/test_experiment_fixtures.py`:
  `23 passed, 17 subtests passed`;
- `python -m json.tool research/beta3-practical-effectiveness/manifest.json`:
  PASS.

These checks establish only the offline protocol and contract integrity. They
do not establish that a model, host, generated program, or execution oracle
has run successfully.
