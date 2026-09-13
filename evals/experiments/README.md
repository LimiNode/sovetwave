# Voice-card selector ablation pilot

This directory contains the design for the first selector-value experiment.
It is deliberately separate from the production routing path and the default
behavioral case suite. No model call is made by the planner.

## Causal contrasts

- **A — dynamic:** the current `select_voice_cards.py` runtime path.
- **B — static-equivalent:** a committed lookup for the same canonical
  `scene/domain` pairs and the same card IDs, with no selector subprocess.
- **C — no-cards:** the slim kernel and domain references without voice cards.

The static map is validated against the current corpus and selector by
`scripts/plan_voice_card_ablation.py`; every canonical pair in the map must
produce the exact same ordered IDs in the dynamic selector. The corpus SHA is
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

Primary metrics are semantic assertion pass rate and first-attempt completion.
Secondary metrics are applicable voice/language axes, input/cached/uncached
input, output/reasoning tokens, tool calls, and elapsed time. The pre-registered
engineering gates allow at most one additional semantic failure or completion
loss per 18 observations, cap positive-case voice/language loss at 5 percentage
points, require B to remove its selector call and reduce median elapsed or
uncached input by at least 10%, and require C to show no material degradation
plus a 10% cost reduction. Any systematic timeout/tool failure or divergence
on negative controls blocks the corresponding simplification. These are pilot
gates, not a formal non-inferiority test.
