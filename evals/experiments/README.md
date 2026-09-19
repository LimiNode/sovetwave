# Voice-card selector ablation pilot (protocol v2)

This directory contains the design for the first selector-value experiment.
It is deliberately separate from the production routing path and the default
behavioral case suite. No model call is made by the planner.
Protocol v2 replaces the production selector paragraph in each ephemeral
skill copy; it never appends a competing selector policy. The replacement is
fail-closed and requires exactly one production selector block.

## Causal contrasts

- **A — dynamic:** invoke `select_voice_cards.py` once with the authoritative
  preregistered `scene/domain` pair; do not infer tags or run `--list-tags`.
- **B — static-equivalent:** a committed lookup for the same fixed
  `scene/domain` pairs and the exact same ordered `id/use/anchor` payload, with
  no selector subprocess.
- **C — no-cards:** the slim kernel and domain references without voice cards.

This is a fixed-tag pilot. It does not measure tag inference or `--list-tags`
vocabulary-discovery cost. Those require a separate production-path study.

The static map is validated against the current corpus and selector by
`scripts/plan_voice_card_ablation.py`; every preregistered positive pair must
produce the exact same ordered `id/use/anchor` payload in the dynamic selector.
The corpus SHA is
recorded so a corpus edit invalidates the map instead of silently changing the
experiment.

## Pilot

The pilot has six behavioral cases: four selector-positive cases (including a
dedicated teaching/explanation case) and two negative controls where the selector is explicitly inapplicable. Three
repetitions produce 54 observations. For case index `i` and repetition `r`,
the arm order is `[A, B, C]` rotated by `(r - 1 + i) mod 3` (1-based `r`,
zero-based `i`), giving 18
observations per arm and balanced first positions.

Generate the plan without invoking a model:

```text
py -3 scripts/plan_voice_card_ablation.py --output evals/experiments/voice-card-selector-ablation-plan.json
```

The generated plan records Git HEAD, dirty state, arm counts, and the
checkpoint/provenance requirements inherited from
`scripts/run_revision_interleaved.py`. A future execution runner must retain
those guarantees and record completion/censoring separately.

Inspect one effective treatment without invoking a model:

```text
py -3 scripts/materialize_voice_card_arms.py --case-id voice-card-selector-teaching-explanation --arm A --json
```

The materializer executes the selector only for eligible A observations. B
uses the committed payload, C carries no payload, and all three arms omit
selector/cards for negative controls. Routing instructions are host context,
not additions to the user prompt.

Before the pilot, run the live execution preflight on the synthetic fixture:

```text
py -3 scripts/run_voice_card_preflight.py --output <preflight.json> --execute --model gpt-5.6-sol --codex-provider-config <config.toml>
```

The preflight is a diagnostic outside the pilot dataset. It must establish
one `fixed_select` for A and zero selector calls for B and C before the pilot
is frozen and started. All three arms use `danger-full-access` inside the same
isolated temporary-workspace boundary because Codex blocks bundled Python
scripts in its restricted sandboxes; the sandbox mode is recorded in every
observation and in run metadata.

The measured runner is opt-in and keeps the A oracle out of the A input:

```text
py -3 scripts/run_voice_card_ablation.py --output <result.json>
```

Without `--execute` this writes only the 54-row dry-run plan. With explicit
`--execute` and a provider configuration, A's selector command runs inside the
Codex session and its JSON event stream is checked for exactly one selector
invocation on each positive observation; B and C are checked for zero. The
runner writes an append-only checkpoint and provenance sidecar, including the
effective ephemeral skill SHA and structured selector trace, and supports
resume only when their metadata matches. Invalid treatment stops the run by
default and is never included in causal metrics.

Primary metrics are `full_observation_pass` and first-attempt completion.
Observations with `treatment_status=invalid` are execution-integrity failures:
they remain in the append-only checkpoint and audit output, but are excluded
from causal comparisons (and stop the runner by default). Pointwise assertion
pass rate is reported as a secondary diagnostic only.
Secondary metrics are applicable voice/language axes, input/cached/uncached
input, output/reasoning tokens, tool calls, and elapsed time. The pre-registered
engineering gates allow at most one additional semantic failure or completion
loss per 18 observations, cap positive-case voice/language loss at 5 percentage
points, require B to remove its selector call and reduce median elapsed or
uncached input by at least 10%, and require C to show no material degradation
plus a 10% cost reduction. Any systematic timeout/tool failure or divergence
on negative controls blocks the corresponding simplification. These are pilot
gates, not a formal non-inferiority test.

## Integral beta.2 benchmark

`sovetwave-integral-benchmark-v1.json` is the frozen selection for the first
cross-capability comparison after the routing and closure-audit changes. It
keeps a 36-case explicit-activation core separate from a 10-case
natural-activation subset, a six-case repository-grounded tool-use pilot, and
three small thematic ablations. The same case manifest and four repetitions
are used for Luna and Terra; run Luna first, then Terra without editing the
manifest. The repository-grounded pilot has three repetitions because its
purpose is trajectory inspection rather than the primary capability estimate.

The manifest is data, not a new runner. Use repeated `--case-id` values from
the frozen lists with `scripts/run_model_evals.py`; keep the resulting JSON,
JSONL checkpoint, model, revision, activation mode, and provider configuration
together. Do not add a case after seeing a model result; a newly discovered
failure becomes a holdout for the next benchmark revision.
