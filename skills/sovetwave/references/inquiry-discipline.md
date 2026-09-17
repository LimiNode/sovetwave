# Inquiry discipline

Use this reference before accepting a consequential conclusion or choosing a
substantial next action when material conditions remain unknown. It complements
`verification-discipline.md`: inquiry finds a missing decision-relevant
question; verification tests the resulting hypothesis or explanation.

## Trigger

Run a short inquiry pass for research, investigation, experiment design,
comparative analysis, architecture choices, incident conclusions, acceptance
or rejection decisions, and other consequential decisions with material
unknowns. Do not invoke it for a routine local fix, a precise syntax error, or a
focused check whose contract and exercised property are already established.

The trigger is not the presence of the word “research”. Use it only when a
plausible answer could change the conclusion, recommended action, architecture
choice, experiment priority, accept/reject decision, or risk assessment.

## Coverage audit

Select only the dimensions that are plausible and decision-relevant. They are
lenses, not a mandatory nine-step checklist:

| Dimension | Question |
| --- | --- |
| `scope / regime` | Does the conclusion hold across the relevant time, load, configuration, subject, or operating regimes? |
| `construct validity` | Does the measurement or operational definition represent the property being claimed? |
| `interaction / layer completeness` | Were components checked together with mechanisms that can change their effect? |
| `alternative mechanism` | Is there another plausible explanation for the observation? |
| `temporal / causal boundary` | Could ordering, leakage, clock, or correlation be mistaken for causation? |
| `coverage` | Which material path, data source, platform, or failure path is absent? |
| `controls / baseline` | Is there a control that separates the claimed effect from background behaviour? |
| `generalisation` | Does the result survive outside the development sample or configuration? |
| `metric alignment` | Does the measured quantity answer the decision the user actually has to make? |

## Inquiry candidate

For each surfaced inquiry, keep the shape compact:

```text
target claim
unassessed dimension
question
why the answer can change the decision
smallest useful evidence or check
coverage state
```

`coverage state` is orthogonal to evidence status. Use:

- `assessed` — the dimension was considered against the stated decision;
- `not_assessed` — the dimension can still change the right to generalise or act;
- `not_applicable` — the dimension has no meaningful interpretation here;
- `blocked` — the dimension is material but the required evidence is currently unavailable.

These states do not mean that the claim is true or false. Keep
`confirmed`, `disproved`, `not reproduced`, and `not checked` for evidence
status in the verification process.

## Operational prerequisites

Before executing a consequential operational instruction, inspect the facts it
quietly assumes. Ask what must already be true for the instruction to have a
defined meaning: the applicable path or environment, required tools, users,
flags, services, configuration, baseline or source of truth, and the expected
observable result. This is a precondition inquiry, not a request for every
possible piece of context.

If a prerequisite can change the action or the interpretation of its result,
surface one bounded question or obtain the fact from an authorized repository
source before acting. If it cannot be established, mark the operation blocked
or the check not checked; do not replace an unknown baseline with “works as
before”, “normal checks”, or “production-like” as if those phrases were
executable contracts. When the task supplies a concrete path, command,
configuration, and success signal, proceed with that bounded contract and do
not invent a broader inquiry.

## Decision-impact filter and stop rule

Prefer the question that could reverse the decision. Next prefer one that
distinguishes the leading competing explanations. If value is comparable,
prefer the cheaper discriminating check. Surface one inquiry by default and no
more than three without a specific reason.

Stop when the applicable dimensions are assessed, explicitly not applicable,
or marked blocked with the consequence recorded. Do not generate questions
merely because they are possible. A decision may proceed with a limitation
when no unresolved inquiry can change the next action at the current boundary.

## Handoff to verification

Inquiry does not verify a claim. Pass the selected candidate to
`verification-discipline.md`, which turns it into a finding, required
conditions, strongest plausible disconfirmation, smallest discriminating check,
and evidence status:

```text
fact
→ candidate conclusion
→ material gap
→ inquiry
→ discriminating verification
→ evidence
→ decision
→ action
```
