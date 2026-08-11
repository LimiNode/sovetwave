# Behavioral evals

This harness compares the same cases without Sovetwave and with it enabled. It is deliberately separate from fixture validation: a green CI job proves that the cases are well formed, not that a particular model followed them.

Run a non-billing plan first:

```powershell
py -3 scripts\run_model_evals.py --provider codex --dry-run
py -3 scripts\run_model_evals.py --provider claude --dry-run
```

Run a live comparison only after selecting the model, account, and spending limit:

```powershell
py -3 scripts\run_model_evals.py --provider codex --model <model>
py -3 scripts\compare_runs.py evals\behavioral\results\<run>.json
```

The Codex adapter creates a temporary workspace for each variant and installs the repository skill only for the Sovetwave run. The Claude adapter uses `--bare`; its Sovetwave variant appends the repository Output Style. Neither adapter enables model tools.

`compare_runs.py` produces a side-by-side Markdown sheet with the human scoring axes from `rubric.json`. Keep completed run artefacts local unless a result is intentionally chosen as a reviewed baseline.
