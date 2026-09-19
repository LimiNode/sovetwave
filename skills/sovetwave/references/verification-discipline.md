# Verification discipline

Use this reference when a diagnosis, review, incident, or design decision must
be separated from a plausible story. It adds a verification layer; it does not
replace language, library, or repository contracts.

## Build the evidence chain

Record the chain explicitly:

```text
finding
→ artifact check
→ mechanism
→ required conditions
→ strongest plausible disconfirmation
→ smallest discriminating check
→ evidence status
```

Start with the observed finding and the artifact that contains it. Explain the
mechanism only as far as the artifact and known contract support it. List the
conditions required for the consequence; an unstated condition remains
unknown. Then state the strongest plausible observation that would make the
current explanation false, followed by the cheapest check that distinguishes
the explanations.

Use one of these evidence statuses:

- `investigation target` — a plausible lead requiring a discriminating check;
- `contract-dependent` — the result depends on a missing or unresolved contract;
- `confirmed` — the evidence establishes the violated rule on the stated path;
- `not reproduced` — the check did not reproduce the finding under its stated setup;
- `disproved` — the proposed explanation is contradicted by the check;
- `not checked` — no relevant verification was run.

Do not promote a suspicion to a confirmed defect merely because its consequence
would be severe. Before increasing confidence, look for the condition under
which the proposed explanation would be false. A passing build, a successful
demo, or a test that exercises another property is not evidence for the missing
property.

## Choose the smallest useful check

Prefer a local reproducer for a local defect, a focused contract test for an
interface property, and a process-level or end-to-end check only when the
route, ownership, and delivery semantics are established. Preserve the exact
command, configuration, input, and relevant output. A check that was not run is
`not checked`, never successful by implication.

For a bounded architecture spike, record both the decision threshold and the
artifact disposition: delete the exploratory code, or promote it after a
separate review. A failed storage experiment does not by itself prove a service
boundary; measure topology concerns separately.

For an unresolved diagnosis, end with the smallest next check that can change
the evidence status. If the relevant property is already established by
sufficient contract or observation, state that boundary and stop.

For an unresolved diagnosis, a discriminating check must use an established
boundary, failure condition, or contract. If the actual limit is unknown,
name the property to discover first; do not invent a concrete threshold,
constant, or protocol rule merely to make the test look specific.

For an explicitly hypothetical case or a user-supplied premise, accept the
stated artifact facts as premises unless they conflict with available evidence;
do not demand repository access merely to replay the premise.

## Negative results and branch closure

A negative result retains the scope of the tested configuration or
intervention. A canonical or reference implementation can establish fidelity
of the particular method it implements, but does not by itself establish
representativeness of the whole family. Promote a failed variant to a failed
method family only when the tested intervention represents the claimed family
scope or multiple independent mechanisms close the material recovery paths.

Before closing a research or design branch, record what is being rejected and
the strongest observation that would show the closure is premature. Check the
cheapest material disconfirmation: a faithful reference, an aligned objective
and operating condition, an independent mechanism, or an upstream-state
comparison that distinguishes new information from duplicated encoding. If
the check is unavailable, narrow the claim and mark the closure unverified;
do not turn the absence of more experiments into evidence that the family is
exhausted.
