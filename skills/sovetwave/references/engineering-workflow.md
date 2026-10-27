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

Read repository instructions and discover only the toolchain facts required by
the selected route before changing code. Before executing a command, establish
its actual package or build entry point, test entry point, CI-relevant check,
and working directory. Do not replace them with a preferred tool or run a
command from an assumed repository root.

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

Treat documentation as part of change impact only when the change touches an
established contract, architecture invariant, required command or procedure,
migration or rollback, API, or user-visible behaviour. In that case find the
normative owner, update or verify it, and check the affected acceptance path.
A private implementation change with none of those effects does not require a
ceremonial documentation update.

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

## Optional task contract / work order

Use a compact task contract when work is autonomous, spans several stages,
crosses an agent handoff, is expected to repeat, or has a formal acceptance
boundary. For a small local change with a known contract, skip this ceremony.

When the contract is useful, record only the fields that materially constrain
the work:

- **goal** — the result to produce;
- **starting context/state** — the relevant revision, artifacts, and known
  observations;
- **constraints and non-goals** — what must remain unchanged and what is out
  of scope;
- **execution autonomy** — edits, commands, checks, or external systems the
  agent may use;
- **publication authority** — separately state whether commit, push, issue or
  PR changes, merge, release, or other external actions are authorized;
- **expected artifact** — the file, patch, report, or handoff to return;
- **acceptance evidence** — the concrete check and observable result that make
  the artifact acceptable;
- **blocked conditions** — missing authority, unavailable prerequisites,
  failed checks, or unresolved contract choices.

Completing the work does not grant publication authority. Do not infer commit,
push, merge, release, or other external permission from execution autonomy or
from the presence of an expected artifact. Do not require a fixed JSON/YAML
schema or a separate Work Order file when a short task description carries the
same distinctions.

## Separate handoff from publication

Handoff states what changed, what was checked, what was not checked, and what
decision remains. Committing, pushing, opening or editing issues and pull
requests, and publishing releases are separate actions. Perform only those
publication steps authorised by the user or required by the established
repository workflow.
