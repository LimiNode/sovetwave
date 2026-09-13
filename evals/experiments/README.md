# Voice-card selector ablation pilot

This directory contains the design for the first selector-value experiment.
It is deliberately separate from the production routing path and the default
behavioral case suite. No model call is made by the planner.

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

The measured runner is opt-in and keeps the A oracle out of the A input:

```text
py -3 scripts/run_voice_card_ablation.py --output <result.json>
```

Without `--execute` this writes only the 54-row dry-run plan. With explicit
`--execute` and a provider configuration, A's selector command runs inside the
Codex session and its JSON event stream is checked for exactly one selector
invocation on each positive observation; B and C are checked for zero. The
runner writes an append-only checkpoint and provenance sidecar and supports
resume only when their metadata matches.

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
