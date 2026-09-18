# Repository instructions for coding agents

Use this reference when creating, restructuring, or reviewing `AGENTS.md`,
`CLAUDE.md`, or an equivalent repository instruction hierarchy. The aim is a
small set of accurate operational contracts, not a general manifesto about AI.

## Establish the real instruction surface

Before proposing a structure:

1. Locate existing repository and directory-scoped instruction files.
2. Inspect the repository tree, build entry points, tests, CI, generated and
   vendored areas, submodules, and normative design documents relevant to the
   task.
3. Distinguish an observed project rule from a proposed convention. Do not
   invent commands, paths, checks, supported platforms, or ownership boundaries.
4. If the host is known, apply its documented instruction scope and precedence.
   If the host is unknown or custom, establish those semantics before relying
   on nested files or filenames.

Known host adapters:

- **Codex**: apply the documented `AGENTS.md` subtree scope and precedence;
  direct system, developer, and user instructions outrank repository files.
- **Claude Code**: use the documented `CLAUDE.md` project-memory discovery
  rules; nested files may enter context when their subtree is accessed, while
  `@path` imports are explicit inclusions.
- **Unknown or custom host**: verify discovery, scope, and precedence before
  treating an instruction file as authoritative.

## Design the hierarchy

Use the root instruction file as a router and repository-wide contract. It may
contain:

- a short repository identity and its important compatibility boundaries;
- rules that apply to every change;
- a task-to-document routing table;
- a verification routing table;
- instruction-ownership and publication boundaries;
- concise cross-cutting safety or submodule rules, when the repository actually
  has those concerns.

Put detailed knowledge in the nearest directory that owns the affected code or
workflow. A child instruction file should add local architecture, invariants,
approved patterns, and focused checks; it should not repeat the root. Create a
child file only when that subtree has enough distinct rules to repay its context
and maintenance cost. A small repository may need only one concise root file.

When a rule constrains callers outside the owning subtree, keep a short
cross-cutting invariant at the root and link to the detailed local rationale.
Choose one normative owner for each rule. Replace duplicated prose with links or
local additions, and resolve contradictions instead of relying on nearest-file
precedence to hide them.

## Write operational rules

For a fragile or non-obvious rule, record the smallest useful contract:

- **scope and trigger**: what files or tasks it governs;
- **preconditions**: what must already be true for the rule to have a defined meaning;
- **invariant**: the behaviour that must remain true;
- **reason**: the concrete failure it prevents;
- **approved path**: the normal alternative to a forbidden pattern;
- **proof**: the focused test, build, static check, or inspection, with an observable success condition;
- **exception owner**: who or what evidence may justify deviation, if applicable.

Do not force this template onto obvious style guidance. Prefer direct commands
over ceremonial severity labels. Preserve exact identifiers and commands.

Do not encode tacit knowledge that exists only in the instruction author's
head. Before accepting a rule such as “run the normal checks”, identify the
working directory, trigger, required tools or services, relevant configuration
and baseline, the bounded action, and the observable result that counts as
success. Obtain those facts from the repository or the authorized task context;
do not guess them. If a prerequisite, source of truth, or expected result is
unknown, record the rule as conditional and ask the smallest decision-relevant
question or report the check as unavailable. “Works correctly” is not an
observable proof by itself.

For a complex operational rule, perform a brief contract pass before saving it:

```text
scope → trigger → preconditions → required action → allowed variation
→ observable success → blocked/failure condition → authority for exception
```

This is a quality check on the instruction, not a requirement that users write
YAML or expose private reasoning. A rule whose preconditions or success signal
remain unresolved is not made precise by adding more prose around it.

## Guidance and enforcement

Use repository instructions for guidance and decision rules. When a hard
boundary is required and the host supports it, use sandboxing, permissions,
tool allow/deny rules, and deterministic checks; a prompt rule alone is not a
security boundary. Keep any workflow explanation in the repository document,
but let the host and checks enforce what they can enforce mechanically.

Move mechanically decidable rules into deterministic checks where practical:
format, generated-file drift, forbidden syntax, paired-document presence,
standalone header compilation, link validation, or submodule pin availability.
Keep semantic decisions in review: ownership, compatibility, rollback,
concurrency, and whether two similar implementations really share one contract.
A grep gate is evidence about text, not proof of runtime semantics.

## Review an instruction hierarchy

Review it as executable project infrastructure:

1. Select representative tasks in different subtrees and list the instructions
   each task would load.
2. Check scope, precedence, contradictions, duplication, and missing routes.
3. Verify every path, command, tool, test name, environment assumption, and
   claimed gate against the repository.
4. Check that public or generated artifacts have a named source of truth.
5. Check that mechanical invariants have automation, or explicitly record why
   they remain manual.
6. Remove generic platform policy, persona rules, fixed response templates, and
   roles that do not map to an actual repository workflow.
7. Re-read the root alone: it should orient an agent without loading detailed
   module state into every task.

Report findings by consequence: a contradictory compatibility rule or invalid
build command is more serious than a long paragraph. Propose the smallest
coherent restructuring and an observable check.

## Common failure modes

- A root file becomes a complete architecture manual and consumes context on
  unrelated tasks.
- A routing section says “read only what is relevant” but names every document
  as mandatory.
- Child files copy the root and drift independently.
- Prose claims a CI gate exists when no workflow executes it.
- A prohibition gives no supported alternative or verification path.
- Generic assistant behaviour displaces repository-specific facts.
- New submodule, release, security, or concurrency policy is added to a project
  that has no corresponding boundary.
- More instruction files are treated as inherently better, even when their
  scopes do not differ.
