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

If Codex uses a local or proxy provider defined in your normal `config.toml`,
pass that configuration explicitly. The harness keeps `--ignore-user-config`
so that unrelated personal defaults do not affect the baseline, but copies the
selected `model_provider` and its `[model_providers.<name>]` section as
per-invocation overrides. It does not read or copy credentials.

```powershell
py -3 scripts\run_model_evals.py `
  --provider codex `
  --model gpt-5.6-terra `
  --codex-provider-config "$env:USERPROFILE\.codex\config.toml" `
  --limit 1 `
  --output evals\behavioral\results\terra-pilot-lb.json
```

Run this pilot from the same PowerShell session in which Codex LB is logged in
and `CODEX_HOME` points to that evaluation login. It does not change the
VSCodium extension or your regular Codex configuration.

Run one named case when validating a specific regression or language rule:

```powershell
py -3 scripts\run_model_evals.py --provider codex --dry-run --case-id russian-pr-status-report
```

The Codex adapter creates a temporary workspace for each variant and installs the repository skill only for the Sovetwave run. The Claude adapter uses `--bare`; its Sovetwave variant appends the repository Output Style. Neither adapter enables model tools.

By default a live run stops on the first failed invocation, so an invalid login or unavailable model does not produce a full set of empty results. Use `--continue-on-error` only when failures themselves are part of the investigation.

`compare_runs.py` produces a side-by-side Markdown sheet with the human scoring axes from `rubric.json`. Apply the [grader contract](graders/grader-contract.md) for a human or LLM score. Keep completed run artefacts local unless a result is intentionally chosen as a reviewed baseline.
