# Behavioral evals

This harness compares the same cases without Sovetwave and with it enabled. It is deliberately separate from fixture validation: a green CI job proves that the cases are well formed, not that a particular model followed them.

Run a non-billing plan first:

```powershell
py -3 scripts\run_model_evals.py --provider codex --dry-run
py -3 scripts\run_model_evals.py --provider claude --dry-run
```

For a standalone Claude installation, use `--claude-full-skill` to measure the
complete project skill together with the output style. The harness places the
skill in the temporary project's `.claude/skills/sovetwave` directory and
passes that project to Claude; without this option a Claude run measures only
the output style layer.

```powershell
py -3 scripts\run_model_evals.py `
  --provider claude `
  --model <model> `
  --claude-full-skill `
  --case-id russian-pr-status-report `
  --dry-run
```

Если Claude Code получает proxy endpoint и credentials из пользовательского
`~/.claude/settings.json`, добавьте `--claude-setting-sources user,project`.
По умолчанию используется только `project`, чтобы не смешивать eval с личными
настройками и skills.

Run a live comparison only after selecting the model, account, and spending limit:

```powershell
py -3 scripts\run_model_evals.py --provider codex --model <model>
py -3 scripts\compare_runs.py evals\behavioral\results\<run>.json
```

If Codex uses a local or proxy provider defined in your normal `config.toml`,
pass that configuration explicitly. The harness keeps `--ignore-user-config`
so that unrelated personal defaults do not affect the baseline, but copies
only the selected provider's non-sensitive endpoint and transport settings as
per-invocation overrides. Credentials must remain in the normal `CODEX_HOME`
mechanism; bearer tokens, static authorization headers, and other sensitive
provider fields are rejected rather than copied or written to result files.

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

Use `--activation natural` to measure an installed skill without injecting the
`$sovetwave` marker into the prompt. The default `explicit` mode is useful for
an intentional activation control; record the activation mode with the run.

Repeat `--case-id` to run an explicit related pair without running the entire
case directory. The runner preserves the requested order:

```powershell
py -3 scripts\run_model_evals.py --provider codex --dry-run `
  --case-id c-small-fixed-temporary-buffer `
  --case-id c-small-temporary-invariance
```

## Case relationships

A derived behavioral case may declare a relation to a base case in the same
suite. The runner checks the relation's schema and references; it does not
judge whether the model's responses satisfy the claimed semantic relation:

```json
"relation": {
  "kind": "invariance",
  "base_case": "c-small-fixed-temporary-buffer"
}
```

Use `contrast` for a paired counterexample or decision contrast that changes a
decision-relevant condition. This project-level relation is broader than a
formal minimal Contrast Set: for a local decision-boundary experiment, vary as
few decision-relevant facts as practical. Use `directional` when the assertions
require that change to move the recommendation, and `invariance` when the
conclusion should survive an irrelevant change. The runner rejects unknown
kinds, missing or cross-suite bases, self-references, and cycles. It records the
declared, schema-validated relation map in the run JSON; `compare_runs.py` shows
an overview and the base beside each derived case. A relation does not add the
base case implicitly: select both IDs when the measurement needs both
responses. Determining whether an invariance, directional, or contrast claim
holds remains evaluator or human work over the responses.

## Thematic-reference ablation

An ablation compares three variants of the same Codex case: baseline, full
Sovetwave, and Sovetwave with one conditional reference removed from its
temporary skill copy. The core skill stays enabled, so the result answers a
narrow question: what the selected thematic reference contributed beyond the
core.

Use at least two repetitions; three is the normal first run. The option is
currently available only for Codex because Claude Output Styles do not load
the repository references independently.

```powershell
py -3 scripts\run_model_evals.py `
  --provider codex `
  --model gpt-5.6-terra `
  --codex-provider-config "$env:USERPROFILE\.codex\config.toml" `
  --case-id cpp-vector-invalidation `
  --ablate-reference cpp-engineering.md `
  --repetitions 3 `
  --output evals\behavioral\results\terra-cpp-ablation.json

py -3 scripts\compare_runs.py evals\behavioral\results\terra-cpp-ablation.json
```

The result records an ablation status: `planned`, `completed`, `partial`, or
`not_tested`. Individual variants use `planned`, `completed`, `failed`,
`invalid_empty_response`, or `timeout`. A live run exits nonzero when any
variant has one of the failure statuses. Do not replace an absent ablation
with a claim that the reference is unnecessary. `completed` means that every
planned ablated repetition completed; a run stopped before later repetitions
is `partial` or `not_tested`. A repeated model run remains a measurement, not
a proof; score each repetition and compare its evidence.

For repeated comparisons, variant order is rotated to reduce position and
temporal bias. With three variants the harness uses the Latin-square cycle
`baseline → full → ablated`, `full → ablated → baseline`,
`ablated → baseline → full`; with two variants it alternates their order.
The planned `variant_orders` and actual per-result `sequence` are written to
JSON and shown in the comparison sheet.
Runs shorter than a complete order cycle are recorded as `order_balance:
partial`; they are valid measurements but not fully counterbalanced.

Supported thematic references are `agent-instructions.md`,
`architecture-decisions.md`, `c-engineering.md`, `code-economy.md`,
`cpp-application-architecture.md`, `cpp-callback-async-lifetime.md`, `cpp-engineering.md`,
`cpp-lifetime-and-queues.md`, `cpp-review-workflow.md`,
`development-workflow-russian.md`, `engineering-workflow.md`,
`house-conventions.md`, `messaging-and-distributed-systems.md`,
`pedagogy-and-dialogue.md`, `python-backend-architecture.md`,
`python-engineering.md`, `qt-cpp-engineering.md`, and `history-and-sources.md`.
The always-loaded voice core is deliberately not
ablatable: removing it would compare different skills rather than isolate a
thematic layer.

For a whole-layer control, use `--ablate-core`. This removes the complete
`SKILL.md` from the temporary styled workspace and records
`sovetwave_without_core`; it is intentionally interpreted as a control against
the installed skill, not as evidence that any individual reference is
unnecessary.

The Codex adapter creates a temporary workspace for each variant and installs the repository skill only for the Sovetwave run. The Claude output-style-only adapter uses `--bare` and enables no model tools. With `--claude-full-skill`, both baseline and Sovetwave use project skill discovery and the same `Skill,Read,Bash` tool and permission surface; only the Sovetwave workspace contains the skill.

By default a live run stops on the first failed, timed-out, or empty invocation,
so an invalid login or unavailable model does not produce a full set of empty
results. Use `--continue-on-error` only when failures themselves are part of
the investigation. Explicit `--case-id` selection cannot be combined with
`--limit`, which prevents a related case pair from being silently truncated.

`compare_runs.py` produces a side-by-side Markdown sheet with the human scoring axes from `rubric.json`. Apply the [grader contract](graders/grader-contract.md) for a human or LLM score. Keep completed run artefacts local unless a result is intentionally chosen as a reviewed baseline.
