# Grader contract

Score each response arm independently on each applicable axis in `../rubric.json`, from 0 to 4. In a Claude three-arm run the arms are vanilla baseline, Sovetwave voice-only, and Sovetwave full skill. Judge technical correctness before voice. A response that invents project facts, omits a safety boundary, changes a formal identifier, or turns an unstated contract into a requirement cannot score above 1 on the affected axis.

Cases may declare `applicable_axes` when an axis has no meaningful interpretation
for that task. Omitted metadata means all rubric axes remain applicable; an empty
or unknown axis list is invalid.

Treat `process_status` and `semantic_status` separately. A completed CLI
process with non-empty text is still `semantic_status: unrated` until the
assertions have been checked. Classify plan-only, premise-refusal, empty, and
task-answer responses explicitly during grading.

The rubric declares hard gates to be applied before preference scoring: a
response that fails technical correctness or a required safety/contract boundary cannot be rescued by voice,
concision, or Russian-language quality. Score each response independently
before any side-by-side comparison; the comparison sheet is not evidence that
one response caused the other. For repeated runs, note disagreements and mark
the relation `unstable` when independent judgements conflict materially.

Use the case assertions as observable checks, not as prose to reward mechanically. Leave an axis blank when it is not relevant to the case; record one short evidence-based note for every score below 3.

For `english_intrusion`, do not penalise a formal identifier, command, path, API or protocol name, tool name, project entity, status code, package name, or established special term. Penalise English that stands in for an equally precise ordinary Russian role, state, action, property, or description.

For `semantic_economy`, judge whether every proposed branch, state, abstraction, duplicate path, and language-level promise is justified by the established requirement. Do not reward compressed or clever code merely for having fewer lines, and do not penalise explicit error handling or readable structure that carries necessary semantics.

For an LLM grader, run one independent pointwise judgement per arm: provide
the prompt, one response with no variant label, the applicable rubric rows,
and this contract. Repeat in separate calls for every arm. A later optional
pairwise pass may see two responses, but it must be reported separately and
run in both orders; disagreement is `unstable`. Require JSON with one object
per axis for each pointwise call:

```json
{"axis": "technical_correctness", "score": 0, "evidence": "short factual reason"}
```

Associate each pointwise result with its arm outside the judged response (for
example, in the harness record). Do not put multiple arm scores in one
pointwise object: that would expose alternatives to a judge that is required
to score only one response.

Do not let the grader infer hidden repository facts, reward historical props, or penalise literal language in a critical context.
