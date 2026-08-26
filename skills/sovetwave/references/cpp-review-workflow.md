# C++ review workflow

Read this reference for a review of C or C++ code, a commit, a pull request, a
directory, or a repository. It defines the investigation procedure. Use
`cpp-engineering.md` for language-level reasoning and `code-economy.md` for the
separate semantic-economy pass.

## Fix the scope before judging the code

Distinguish a changed-lines review from a file, subsystem, or repository audit.
For a diff review, inspect enough callers, declarations, tests, and surrounding
control flow to understand the change, but report an unchanged defect only when
the change introduces it, exposes it, depends on it, or the user requested a
wider audit. Do not turn a bounded review into a backlog inventory.

A request to review is read-only. Do not edit files, apply formatting, update
generated artefacts, or publish changes unless the user separately requests a
fix or publication.

Establish the project profile from repository evidence:

- application or executable;
- private library used in one build;
- public or header-only library with source-compatibility obligations;
- shared library or plugin with an ABI boundary;
- compatibility-stable framework with an explicit release policy.

Names such as `core`, `framework`, or `plugin` are not proof of a compatibility
contract. Inspect public headers, exports, packaging, consumers, version policy,
and build targets before applying stricter rules.

## Collect deterministic evidence first

Discover the project's own build and test entry points. Prefer its configured
compiler warnings, tests, sanitizers, static analyzers, formatting checks, and
CI commands over a generic replacement. Run the narrowest safe checks that
cover the reviewed surface, then broaden in proportion to risk and cost.

Treat tool output according to what the tool proves:

- a compiler error or sanitizer trace is evidence for the reported path;
- a clean run covers only the executed configuration and inputs;
- a textual or regular-expression scanner reports a pattern, not its semantics;
- static-analysis output is a lead until the relevant control flow, ownership,
  caller, or contract confirms it;
- an unavailable or failed check is `not run`, never a passing result.

Do not suppress a confirmed tool finding merely because the model dislikes it,
and do not call a heuristic finding confirmed merely because a script printed
it. Preserve the command, configuration, and relevant output needed to reproduce
the observation.

## Perform semantic passes

After collecting deterministic evidence, inspect the code in bounded passes:

1. **Lifetime and ownership**: owners, aliases, invalidation, exception and
   error exits, allocation/deallocation boundaries, callbacks and views.
2. **Concurrency**: all conflicting reads and writes, thread affinity,
   synchronisation ownership, waiting and shutdown contracts.
3. **API and compatibility**: public declarations, source compatibility,
   ABI only where an ABI contract exists, serialization and plugin boundaries.
4. **Errors and recovery**: validated inputs, partial work, rollback, resource
   release, error propagation, cancellation and observable failure.
5. **Performance and semantic economy**: only after correctness; identify
   repeated work, detach/allocation, dead residue, duplicate invariants, and
   measured hot paths without inventing caches or frameworks.

These are review passes, not a requirement to launch a fixed number of agents.
Combine or omit a pass only when it is genuinely inapplicable, and say what was
not checked when that affects confidence in the result.

## Consolidate findings

Deduplicate findings that share the same mechanism and repair boundary. For each
reported item, include evidence, consequence, the smallest justified correction,
and a focused verification.

Classify without invented percentages:

- **confirmed defect**: repository evidence establishes the violated rule or
  invariant;
- **contract-dependent property**: correctness depends on an unstated or
  unresolved requirement;
- **investigation target**: evidence indicates a plausible defect, but a caller,
  build fact, runtime trace, or design decision is still missing.

Prioritise by consequence and reach, not by stylistic dislike. Do not hide an
important investigation target among confirmed defects, and do not inflate a
style preference into a correctness finding. If the requested scope is clean,
say so and state the checks and limits; never manufacture findings to fill a
report.
