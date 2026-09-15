# Project documentation

Read this reference when a task creates, changes, reviews, or relies on
project documentation: contracts, ADRs, plans, research notes, architecture
documents, runbooks, or a README whose claims may have drifted.

## Treat documentation as evidence and memory

Documentation is part of the project's evidence chain and institutional
memory, not decorative prose. First discover the existing documentation
topology: file locations, indexes, templates, lifecycle markers, owners, and
the checks that publish or validate it. Do not introduce a new documentation
tree or mandatory file because another project has one.

For each fact, identify its normative owner. Code is evidence of the current
implementation; tests are evidence of exercised expectations; a contract is
the external promise; an ADR owns durable rationale; a plan owns intended
work. If these sources disagree, report the conflict and the scope of each
source. Do not silently choose whichever file was read first.

Document what cannot be recovered reliably from the implementation alone:

- intent, constraints, and the rationale for a durable choice;
- invariants, exceptions, acceptance criteria, and operating modes;
- migration, compatibility, rollback, and recovery procedures;
- decisions and evidence that a future maintainer would otherwise have to
  rediscover.

Do not mechanically duplicate names, signatures, or control flow that the
repository can expose directly. Prefer one normative source with links from
secondary explanations. Move mechanically checkable invariants into tests,
linters, schemas, or other tooling; retain semantic judgement and justified
exceptions for review.

## Choose the document by the decision

Use the smallest durable form that owns the information:

| Decision or information | Suitable form |
| --- | --- |
| External or cross-component promise | contract |
| Durable architectural choice and rationale | ADR |
| Ordered intended work and acceptance criteria | feature plan |
| Bounded investigation and its evidence | research note |
| Repeatable operation, incident, migration, or rollback | runbook |
| Stable system boundaries and relationships | architecture document |

A short local note is enough for a transient observation. A reversible private
change with no durable decision does not need a ceremonial ADR. Create a
long-lived document when it owns a decision, contract, procedure, or evidence
that will outlive the change.

## Mark epistemic status explicitly

Keep lifecycle and truth status separate. Use these statuses when a claim can
be mistaken for an implementation fact:

- `implemented` — supported by the current code path;
- `verified` — supported by a named check, test, or observed operation;
- `contractual` — a normative external or cross-component promise;
- `intended` — stated in a plan, proposal, or ADR but not established as done;
- `stale-suspected` — conflicts with an observed system and needs resolution;
- `superseded` — explicitly replaced by a newer decision or contract;
- `unknown` — current applicability or truth has not been established.

Do not collapse `unknown` into `implemented`, and do not present a README or
active plan as proof that behaviour exists. When status matters, name the
source, revision or review date, and the check that supports `verified`.

For durable documents, use a lifecycle such as `draft`, `active`,
`superseded`, or `archived`. For an ADR, master plan, long-lived contract, or
runbook, record at least `scope`, `owner`, `last-reviewed`, and `review-trigger`.
Do not impose those fields on every short note when they add no decision value.

## Include documentation in change impact proportionally

Consider documentation part of the affected surface when a change touches an
existing documented contract, an architecture invariant, a required command or
procedure, migration or rollback, or user-visible behaviour. Locate the
normative owner, update it or record why it remains accurate, and check links
and acceptance criteria at the same boundary.

A private local refactor with no such impact does not require a documentation
edit merely because the repository contains documentation. If the owner is
unclear or sources conflict, stop short of declaring the documentation
current: state the conflict, proposed owner, and smallest resolution check.
