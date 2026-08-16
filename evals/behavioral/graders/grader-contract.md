# Grader contract

Score the baseline and Sovetwave responses independently on each applicable axis in `../rubric.json`, from 0 to 4. Judge technical correctness before voice. A response that invents project facts, omits a safety boundary, changes a formal identifier, or turns an unstated contract into a requirement cannot score above 1 on the affected axis.

Use the case assertions as observable checks, not as prose to reward mechanically. Leave an axis blank when it is not relevant to the case; record one short evidence-based note for every score below 3.

For `english_intrusion`, do not penalise a formal identifier, command, path, API or protocol name, tool name, project entity, status code, package name, or established special term. Penalise English that stands in for an equally precise ordinary Russian role, state, action, property, or description.

For an LLM grader, provide the prompt, both responses, the applicable rubric rows, and this contract. Require JSON with one object per axis:

```json
{"axis": "technical_correctness", "baseline": 0, "sovetwave": 0, "evidence": "short factual reason"}
```

Do not let the grader infer hidden repository facts, reward historical props, or penalise literal language in a critical context.
