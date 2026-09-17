# Behavioral evals

This harness compares the same cases under controlled agent environments. It is deliberately separate from fixture validation: a green CI job proves that the cases are well formed, not that a particular model followed them.

Cases declare an `execution_mode`:

* `prompt_only` (the default) asks a self-contained technical question. Claude is not put into Plan mode, and every arm receives the same minimal `Skill` tool surface.
* `repository_grounded` supplies a real fixture repository. Every arm receives `Skill,Read,Bash`, the fixture is mounted with `--add-dir`, and Claude uses `dontAsk` so permissions do not turn the answer into a plan-only reply.

Run a non-billing dry-run first:

```powershell
py -3 scripts\run_model_evals.py --provider codex --dry-run
py -3 scripts\run_model_evals.py --provider claude --dry-run
```

For a standalone Claude installation, use `--claude-full-skill` to run three
Claude arms: vanilla baseline, output-style-only, and full skill plus output
style. Without this option, Claude runs the two-arm vanilla vs output-style
comparison. The project skill is placed in the temporary project's
`.claude/skills/sovetwave` directory only for the full-skill arm. Use three
repetitions for a complete three-arm Latin-square cycle; use at least four
repetitions for the two-arm comparison when you want equal first positions.

```powershell
py -3 scripts\run_model_evals.py `
  --provider claude `
  --model <model> `
  --claude-full-skill `
  --repetitions 3 `
  --case-id russian-pr-status-report `
  --dry-run
```

Если Claude Code получает proxy endpoint и credentials из пользовательского
`~/.claude/settings.json`, передайте этот файл через `--claude-settings`.
Раннер скопирует только поля `env` и `model` во временный project settings,
сохранив proxy и исключив личные skills и плагины. Если файл не передан,
можно использовать `--claude-setting-sources user,project`, но такой режим
не изолирует пользовательские skills.

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

## Capability stages

A suite or individual case may declare one primary `capability_stage`:

```json
"capability_stage": "inquiry"
```

The closed vocabulary is `instruction_interpretation`, `grounding`, `inquiry`,
`action_selection`, `implementation`, `verification_selection`,
`evidence_interpretation`, `reporting`, and `voice_realization`. A case-level
value overrides the suite default. The field classifies the principal agent
capability exercised by the case; it is not a semantic score and does not say
that earlier or later stages are irrelevant. Existing unclassified cases remain
valid so historical fixtures do not acquire retrospective labels without
review.

Run output records the resolved classification on each observation and in the
top-level `case_capability_stages` map. `compare_runs.py` reports classified
coverage separately from model quality, including an explicit `unclassified`
count. For revision-interleaved runs, where one top-level classification could
hide a revision difference, the renderer derives the stage from observation
rows: one unique value is used, conflicting values are shown as
`mixed / revision-dependent`, and absent values remain `unclassified`.

## Diagnostic coverage metadata

Suites and cases may also declare two optional diagnostic fields:

```json
{
  "decision_impact": "high",
  "evidence_access": "repository_inferable"
}
```

`decision_impact` uses the closed vocabulary `low`, `medium`, `high`.
`evidence_access` uses `direct`, `repository_inferable`, `executable`,
`external_required`, or `unavailable`. A case-level value overrides its suite
default. Both fields are optional; legacy cases remain unclassified until they
receive an explicit review rather than acquiring subjective labels
automatically.

The runner records the resolved values on each observation and in the
top-level `case_decision_impacts` and `case_evidence_access` maps. The review
bundle and `observations.csv` retain the same fields. `compare_runs.py` renders
separate coverage sections for capability stage, decision impact, and evidence
access. Coverage is metadata about what was exercised and how evidence is
available; it is not a model score, semantic verdict, or assertion replacement.
For revision-interleaved runs, the renderer resolves these fields from the
observation rows: one unique value is used, conflicting values are shown as
`mixed / revision-dependent`, and missing values remain `unclassified`.

The `cpp-insertion-contrast` suite contains a paired `emplace`/`try_emplace`
case. The pair is deliberately about the library contract: `emplace` may
construct a mapped value for an existing key and may move a supplied rvalue;
the no-construction-on-existing-key guarantee belongs to `try_emplace` when
constructor arguments are passed. Grade the exact overload and mapped type,
not the operation name in isolation.

The `verification-neutral-holdouts` suite contains prompts that exercise the
same verification discipline without naming its internal vocabulary. Use it
as a neutral holdout when measuring whether the behaviour generalises beyond
explicitly signposted cases.

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

For an independent review packet, use the checked-in bundle builder after a
run completes. It keeps unknown legacy telemetry as `null`, retains recovery
metadata (`attempt`, `recovered`, and `original_process_status`), and computes
token summaries only from completed invocations:

```powershell
py -3 scripts\build_bundle.py `
  --output-dir <review-directory> `
  --run routing=REVISION=evals\behavioral\results\routing.json `
  --run ablation=REVISION=evals\behavioral\results\ablation.json
```

Every live invocation is also appended to a JSONL checkpoint (by default next
to the requested output) and a readable `.partial.json` snapshot is refreshed
after each variant. The console prints the case, repetition, arm, process
status, and semantic status. If a run is interrupted, repeat the command with
`--resume` to skip the invocations already present in the checkpoint. The
checkpoint is retained as an audit trail after a successful run.

Each result records the requested and resolved model when the CLI reports it,
the provider, skill revision, dirty-tree flag, attempt number, recovery flag,
reported tokens, and elapsed time. Reference-file tracing is recorded as
`not_available` when
the provider stream does not expose file-level tool inputs; an empty list must
not be interpreted as proof that no reference was read.
Codex runs also request the JSON event stream and retain non-secret structured
usage when the provider exposes it (`input_tokens`, `cached_input_tokens`,
`cache_write_input_tokens`, `output_tokens`, and `reasoning_output_tokens`).
Unknown event shapes are
ignored and the stderr token count remains a legacy fallback. Event parsing is
telemetry only; the final answer still comes from `--output-last-message`.
Process completion, semantic quality, and runtime/token cost are separate
measurements. A recovered response must not silently replace the original
failure in an audit: retry failed invocations into a separate JSONL file with:

```powershell
py -3 scripts\retry_failed_evals.py `
  evals\behavioral\results\<run>.jsonl `
  --output evals\behavioral\results\<run>-retries.jsonl `
  --codex-provider-config "$env:USERPROFILE\.codex\config.toml"
```

Retries are Codex-only and select only executed failure statuses. Planned or
unknown observations are rejected rather than converted into live calls. The
utility also fails closed if the recorded revision or material-input state
cannot be matched, or if the current prompt, assertions, execution mode, or
fixture identity differs. Use `--allow-revision-change` only when a revision or
dirty-input change is intentional and must be documented. Recovery output must
be a new file distinct from the source; an existing audit file is never
overwritten. Every failed observation passes this preflight before the first
model call or output-file creation.

Use the original run for first-attempt reliability and the retry file for a
recovery sensitivity analysis. Do not pool recovered observations with the
first-attempt completion rate without reporting the retry rate and selection
rule.

The runner also records a conservative service-level `semantic_class` before
human grading: `task_answer`, `plan_only`, `premise_refusal`,
`tool_failure_answer`, `partial`, or `empty`. This classification is a routing
aid, not a semantic score; assertions and the grader contract remain the source
of truth for answer quality.

Supported thematic references are `agent-instructions.md`,
`architecture-decisions.md`, `c-engineering.md`, `code-economy.md`,
`cpp-application-architecture.md`, `cpp-callback-async-lifetime.md`, `cpp-engineering.md`,
`cpp-lifetime-and-queues.md`, `cpp-review-workflow.md`,
`development-workflow-russian.md`, `engineering-workflow.md`,
`house-conventions.md`, `messaging-and-distributed-systems.md`,
`pedagogy-and-dialogue.md`, `python-backend-architecture.md`,
`python-engineering.md`, `qt-cpp-engineering.md`, `verification-discipline.md`,
and `history-and-sources.md`.
The always-loaded voice core is deliberately not
ablatable: removing it would compare different skills rather than isolate a
thematic layer.

For a whole-layer control, use `--ablate-core`. This removes the complete
`SKILL.md` from the temporary styled workspace and records
`sovetwave_without_core`; it is intentionally interpreted as a control against
the installed skill, not as evidence that any individual reference is
unnecessary.

The Codex adapter creates a temporary workspace for each variant and installs the repository skill only for the Sovetwave run. Claude's three-arm mode uses the same tool surface for vanilla, voice-only, and full-skill arms; only the full-skill workspace contains the project skill. Prompt-only cases omit `--permission-mode`; repository-grounded cases use `dontAsk` with an isolated fixture.

Every Claude invocation uses `--output-format stream-json --verbose`. The run
JSON records observed tool names, whether the project skill was available, and
whether a `Skill` tool call occurred. `status`/`process_status` describe the
CLI process; `semantic_status` is `unrated` until a human or LLM grader checks
the assertions.

By default a live run stops on the first failed, timed-out, or empty invocation,
so an invalid login or unavailable model does not produce a full set of empty
results. Use `--continue-on-error` only when failures themselves are part of
the investigation. Explicit `--case-id` selection cannot be combined with
`--limit`, which prevents a related case pair from being silently truncated.

`compare_runs.py` produces a side-by-side Markdown sheet with the human scoring axes from `rubric.json`. Apply the [grader contract](graders/grader-contract.md) for a human or LLM score. Keep completed run artefacts local unless a result is intentionally chosen as a reviewed baseline.
