# Python backend architecture

Read this reference when designing or changing the architecture of a Python
application, service, command-line program, bot, worker, or data-processing
system. The user may ask for a project rather than an architecture document;
offer a suitable structure when it materially affects the implementation, but
do not turn every Python task into a backend stack.

## Begin with one observable path

Establish one representative path from an inbound boundary through application
rules and state changes to an observable response or external effect. The
inbound boundary may be HTTP, a bot update, CLI arguments, a scheduled job, a
queue message, or an in-process call. HTTP is not the definition of a backend.

Identify which boundary owns input validation, authorization, the application
operation, transaction completion, error translation, and shutdown. Keep
framework request objects, ORM sessions, and transport-shaped errors out of
application rules unless the existing project deliberately treats them as its
contract.

For brownfield work, continue a coherent established path. If the project
already uses SQLAlchemy and Alembic consistently, adding one compatible model,
query, and migration is usually smaller than introducing a parallel data
layer. A new architecture needs a concrete failure of the current one, not a
preference for another framework.

## Choose storage from the required contract

Choose the least costly storage boundary that meets present requirements:

- a file or SQLite for bounded local state with a suitable concurrency and
  recovery contract;
- direct SQL when explicit queries and database behaviour are central;
- a query builder when composable SQL is useful without object mapping;
- an ORM when identity, relationships, unit-of-work behaviour, and the existing
  team or codebase justify it;
- an external store when availability, sharing, volume, or operations require
  a separate service.

Do not add a repository interface merely to hide a library name. Add a boundary
when it owns a meaningful application contract, isolates an external system,
or provides a useful test seam. Keep database-specific behaviour visible where
correctness depends on it.

## Make transactions and migrations explicit

Place a transaction around the state change that must commit or roll back as
one unit. The application operation should determine the business unit; the
entry point or a small transaction owner may supply its execution context.
Do not scatter commits through helpers or imply that an exception rolls back
an already completed external effect.

A database transaction cannot atomically cover an unrelated HTTP API, broker,
or filesystem without an established coordination mechanism. If the contract
requires reliable cross-system work, reason explicitly about idempotency,
outbox or inbox state, retries, reconciliation, and observable failure. Add
only the mechanism required by that contract.

Treat schema migrations, persistent identifiers, and data formats as
compatibility decisions. Establish rollout order, mixed-version behaviour,
backfill, rollback or forward repair, and the authoritative migration tool.
Do not silently choose destructive migration semantics.

## Place background work by lifecycle

Keep short work in the current process when its latency, failure, and shutdown
contract allow it. Use an owned in-process task only when the process can
supervise it and losing it on restart is acceptable. Choose a durable or
supervised execution boundary only when work must survive, scale, retry, or
deploy independently; a worker or queue is one possible mechanism when its
acceptance and delivery contract fits.

Define who accepts work, who owns it after acceptance, how failure is reported,
what happens on shutdown, and whether duplicate execution is allowed. A
five-minute operation is evidence about lifecycle, not by itself a command to
install a particular queue.

## Keep external and deployment boundaries honest

Wrap an external service at the point where authentication, timeouts, error
translation, rate limits, or test substitution form an application contract.
Do not mirror every SDK method behind a pass-through abstraction. Define retry
and idempotency only for operations whose failure classification supports it.

Architecture includes the runtime shape: process entry points, configuration
and secrets, worker count, connection ownership, startup and shutdown,
health checks, observability required for the failure contract, and deployment
units. Do not introduce containers, a service split, structured logging, or a
platform merely as a completeness ritual.

Recommend the smallest coherent shape. Choose reversible module and function
boundaries directly. For a database, public API, migration policy, broker, or
deployment split with durable consequences, surface a direction and its
assumptions. If the user explicitly delegates the choice and the constraints
are established, choose and record it; otherwise ask for the user's decision
before implementation commits to it.
