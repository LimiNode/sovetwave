# Architecture decisions

Read this reference for architecture advice, a new subsystem, a structural
change, or a design choice whose cost extends beyond a local implementation.
Architecture advice may precede any implementation request.

## Establish the decision

State the user-visible goal, current constraints, known future commitments, and
non-goals. Separate an architecture decision from an implementation plan: first
choose ownership and boundaries; only then map them to files and tasks.

For a brownfield project, inspect the existing dependency direction, state
owners, entry points, integration boundaries, deployment model, and tests.
Inherit a coherent established structure unless the task exposes a concrete
failure it cannot support. Do not introduce a parallel architecture beside the
one already in use.

For a greenfield project, begin with the smallest shape that supports the first
observable vertical path. Add a boundary only when it owns a real decision,
state, failure mode, compatibility promise, or independently testable contract.

## Scale the decision process

- **Cheap and reversible:** choose the option that follows current evidence,
  explain why, and proceed without manufacturing alternatives.
- **Moderately costly:** recommend one direction and name a materially different
  alternative together with the condition that would make it preferable.
- **Expensive or hard to reverse:** present the decision, consequences, and
  recommendation. If the user has explicitly delegated this choice and the
  material constraints are established, choose and record it; otherwise obtain
  the user's choice before committing to it. Public APIs, persistent formats,
  migrations, ABI, deployment topology, and external integrations normally
  belong here.
- **Critical fact unknown:** run or propose a bounded spike before deciding.

Judge cost and reversibility, not whether a choice has an architectural label.
Do not hand the user three decorative options when one clearly follows the
existing system. Do not silently choose an expensive compatibility contract.

## Compare what changes the decision

Compare only material differences: ownership and lifetime, dependency
direction, data and transaction boundaries, event or call flow, concurrency and
shutdown, compatibility, deployment and operability, test seams, team
familiarity, and migration cost. Extensibility and scalability are not benefits
without a relevant future requirement or measured constraint.

Give a recommendation in actionable form: choose X because of the established
constraints; choose Y only if a named requirement appears; identify the next
observation that could overturn the choice.

## Use a spike as an experiment

A spike answers one expensive unknown. Define the question, the smallest
representative path, the measurement or compatibility check, the decision
threshold, and the disposition of the exploratory artifact. After measurement,
delete the spike or deliberately promote it to production/test infrastructure
only through a separate review. Do not let exploratory code become production
architecture merely because it already exists.

Failure of a storage or durability property does not by itself prove that
services must be split. Establish the storage decision first; discuss service
topology separately against its own measured boundary and operational contract.

## Refuse architecture inflation

A small utility may need only separated input, operation, and output. A new
service does not automatically need layers, repositories, queues, plugins,
dependency injection, or a framework. Require each boundary to own a present
contract. Prefer a lean recommendation over a diagram whose boxes do not change
any engineering decision.

## Specialize against established invariants

Specialization is a valid architectural choice when it deliberately narrows the
supported world and the narrower contract is real. Before accepting a fast path
that assumes a schema, layout, ordering, bounded size, or operating regime,
state:

- which general behaviour or input class is being excluded;
- which invariant makes the specialization sound and where that invariant is
  established or enforced;
- what happens when the invariant is violated (reject, fallback, diagnostic, or
  another explicit failure mode);
- how the assumption is scoped in time or version and how drift is detected.

Do not require a universal implementation merely because a specialized one is
narrow. Do require an authoritative boundary before the specialized path, and
do not treat a comment, a stable staging sample, or debug-only assertions as
that boundary. If the repository has an explicit owner for the contract, name
it; otherwise identify the enforcing schema, version gate, or input boundary.

Encode established knowledge explicitly when it removes repeated runtime work,
but keep benchmark claims honest about validation, generality, and failure
semantics that the specialized path no longer provides.
