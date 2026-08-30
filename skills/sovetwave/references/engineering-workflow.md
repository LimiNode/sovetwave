# Engineering workflow

Read this reference when implementing, fixing, refactoring, validating, or
handing off a project change. Scale the procedure to the task; the workflow is
not a fixed ceremony.

## Choose the smallest sufficient route

Classify the change by reach, uncertainty, reversibility, and cost of error.

- For a small local change with a known contract, inspect the affected path,
  make the coherent edit, run the narrow check, and report the result.
- For a bounded multi-file or behavioural change, establish the goal and
  non-goals, trace one representative path, plan the necessary increments,
  validate each increment locally, then run the configured checks that cover
  the affected boundary.
- For a public interface, persistent-data, deployment, compatibility,
  concurrency, lifecycle, security, or cross-system decision, establish the
  architecture or run a decision spike before writing a file-by-file plan.

Do not require a comprehensive plan, architecture document, report file, or
fixed stage list for a change that does not need one. Create persistent planning
or decision artefacts only when the repository workflow or user requires them.

## Prime the relevant path

Read repository instructions and discover the actual toolchain before changing
code. Establish the supported versions, package or build entry point, test
entry point, CI-relevant checks, and the working directory required by each
command. Do not replace them with a preferred tool or run a command from an
assumed repository root.

Trace one vertical path from an input or caller through the operation and state
boundary to an observable result and its test. Read adjacent callers, contracts,
and helpers that determine the change. Do not read the whole repository merely
to claim that it was primed.

## Implement with local evidence

Keep each increment coherent enough to check. After an increment, run the
narrowest command that can fail for its mechanism. Before handoff, broaden to
the repository's configured suite in proportion to the affected surface and
risk. A formatter, type checker, unit test, package build, integration test, and
deployment check prove different things; do not substitute one for another.

Record an unavailable, skipped, failed, or out-of-scope check honestly. Do not
invent a coverage threshold, documentation task, logging layer, or validation
tool that the requirement and repository do not establish.

## Review the result

Compare the result with the requested behaviour, local conventions, and the
existing path. Search for duplicate implementations, newly unreachable code,
unhandled failure paths, and accidental public-contract changes. Record any
deviation from the plan with its reason and consequence instead of forcing the
implementation back into an obsolete plan.

Treat review findings as evidence to verify, not an unconditional work order.
Confirm the cited path and contract; fix a supported finding, reject an
unsupported one with evidence, and keep a contract-dependent request
conditional. Re-run the check that can demonstrate the correction.

## Separate handoff from publication

Handoff states what changed, what was checked, what was not checked, and what
decision remains. Committing, pushing, opening or editing issues and pull
requests, and publishing releases are separate actions. Perform only those
publication steps authorised by the user or required by the established
repository workflow.
