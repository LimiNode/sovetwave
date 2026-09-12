# Grader contract

Score the baseline and Sovetwave responses independently on each applicable axis in `../rubric.json`, from 0 to 4. Judge technical correctness before voice. A response that invents project facts, omits a safety boundary, changes a formal identifier, or turns an unstated contract into a requirement cannot score above 1 on the affected axis.

The rubric declares hard gates to be applied before preference scoring: a
response that fails technical correctness or a required safety/contract boundary cannot be rescued by voice,
concision, or Russian-language quality. Score each response independently
before any side-by-side comparison; the comparison sheet is not evidence that
one response caused the other. For repeated runs, note disagreements and mark
the relation `unstable` when independent judgements conflict materially.

Use the case assertions as observable checks, not as prose to reward mechanically. Leave an axis blank when it is not relevant to the case; record one short evidence-based note for every score below 3.

For `english_intrusion`, do not penalise a formal identifier, command, path, API or protocol name, tool name, project entity, status code, package name, or established special term. Penalise English that stands in for an equally precise ordinary Russian role, state, action, property, or description.

For `semantic_economy`, judge whether every proposed branch, state, abstraction, duplicate path, and language-level promise is justified by the established requirement. Do not reward compressed or clever code merely for having fewer lines, and do not penalise explicit error handling or readable structure that carries necessary semantics.

For an LLM grader, run two independent pointwise judgements: provide the prompt,
one response with no variant label, the applicable rubric rows, and this
contract. Repeat for the other response in a separate call. A later optional
pairwise pass may see both responses, but it must be reported separately and
run in both orders; disagreement is `unstable`. Require JSON with one object
per axis for each pointwise call:

```json
{"axis": "technical_correctness", "score": 0, "evidence": "short factual reason"}
```

Associate each pointwise result with its variant outside the judged response
(for example, in the harness record). Do not put `baseline` and `sovetwave`
scores in one pointwise object: that would expose both alternatives to a judge
that is required to score only one response.

Do not let the grader infer hidden repository facts, reward historical props, or penalise literal language in a critical context.
