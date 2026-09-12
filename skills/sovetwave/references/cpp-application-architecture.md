# C++ application architecture

Read this reference when designing or changing the structure of a C++
application, library, plugin, event-driven runtime, UI program, service, daemon,
or embedded target. Apply `cpp-engineering.md` to the language-level contracts
and `cpp-review-workflow.md` when the request is a review.

## Establish the target profile

Identify the build and deployment unit before selecting conventions:

- an application or executable with private implementation;
- a private, public, or header-only library;
- a shared library or plugin with a real ABI boundary;
- an event-driven or long-running runtime system;
- a Qt or immediate-mode UI application;
- an embedded target, service, or daemon with an explicit lifecycle.

Profiles may combine, but their contracts do not spread automatically. A
private application class does not need framework ABI machinery. A shared
library name does not prove a stable ABI. A UI program does not need MVC merely
because its windows can be labelled view and controller.

For brownfield work, trace one executable path and preserve a coherent existing
dependency direction. For greenfield work, begin with the smallest vertical
path that accepts one input or user intent, performs one application operation,
changes owned state, and exposes one result.

## Make ownership and instance identity visible

For every long-lived subsystem, state who constructs it, whether the process may
contain one or many instances, who may observe it, and who destroys it. Prefer
an application composition root that creates owners and passes explicit
non-owning access. Do not turn process lifetime into a default service locator
or singleton when tests, multiple documents, reconnects, plugins, or embedded
instances need isolation.

State that belongs to one provider, window, document, session, or controller
must normally live with that instance. A function-local static callback, cache,
selection, or status slot is shared across every instance that reaches it.
Use shared state only when process-wide sharing is the established contract and
its reset, synchronisation, and shutdown semantics are defined.

Choose pointer and handle forms after the owner and lifetime are established.
Smart pointers do not determine the architecture by themselves. Keep callback
target lifetime, pending operations, and queued delivery as separate contracts
even after storage has been moved into the owning object.

## Draw dependency and event flow

Keep platform and UI details pointing toward application operations rather than
letting domain state depend on widgets, windows, transports, or global event
objects. Separate presentation, application coordination, and domain rules only
where each owns a different decision or state. A small application may express
the same direction with ordinary classes and functions rather than named layers.

Use a direct call when the caller knows the operation and needs its result. Use
a callback or signal for a bounded observer relationship. Introduce an event
queue or bus only when fan-out, temporal decoupling, cross-thread delivery, or
independent extension is required. Define event ownership, ordering, reentrancy,
unsubscribe behaviour, failure visibility, and shutdown; an `EventBus` name
does not establish any of them.

When introducing a new message taxonomy, distinguish requested work from an
established occurrence—often command versus event. Preserve a coherent
existing project vocabulary; do not rename messages merely to enforce these
labels. Do not broadcast mutable domain objects merely to avoid choosing an
owner. Keep synchronous and deferred paths distinguishable in the API and
tests.

## Define threads and shutdown together

Assign each mutable state owner to a thread or synchronization boundary.
Workers may produce owned results or immutable snapshots for the application or
UI owner to consume. Do not let a background callback mutate UI or application
state concurrently merely because the callback type permits it.

Write shutdown in dependency order: stop accepting new work, disconnect or
quiesce producers, signal owned operations, drain or cancel according to the
contract, join workers, release consumers, then destroy their dependencies.
Bound waits where the product has a shutdown deadline. A destructor is not a
shutdown design if callbacks can still arrive while its members disappear.

Test the transition, not only steady state: close with pending work, late
callback, failed initialization, repeated start/stop, and destruction of two
independent instances where those paths are supported.

## Keep immediate-mode UI state in the right lifetime

An immediate-mode render function is called again each frame; it is not the
owner merely because widget code appears there. Keep persistent selection,
draft input, modal state, pending commands, and domain data in an explicit
application, document, window, or view-state owner according to their lifetime.
Keep frame-local labels, temporary layout values, and borrowed draw inputs
transient unless the library contract establishes a longer lifetime.

Let the UI translate user gestures into application operations and render a
stable view of the resulting state. Do not put durable business transitions in
the drawing path when they need independent tests, retries, or non-UI callers.
Conversely, do not add a controller hierarchy when one window can call one
application operation directly and the dependency direction remains clear.

For multiple windows or documents, verify state isolation and stable widget
identity. For background work, publish an owned result or snapshot at a defined
boundary; do not concurrently mutate containers being traversed during a frame.
Keep library-specific context, thread, and frame-lifetime rules alongside these
general ownership rules.

## Introduce compatibility and extension deliberately

Use plugins when independent deployment, third-party extension, optional
components, or a stable extension boundary is a present requirement. First
consider static registration or ordinary composition for features shipped and
rebuilt together. A plugin boundary adds discovery, version negotiation,
ownership across modules, error isolation, packaging, and ABI or C-API design.

For a real public C++ ABI, establish compiler, standard-library, build-option,
allocation, exception, RTTI, and versioning policy. Prefer a narrow C boundary
or opaque handles when the compatibility requirement crosses toolchains. Put
that durable choice to the user; do not smuggle it into a private refactor.

Expose test seams at owned boundaries: an application operation callable
without the UI, a controllable clock or transport where behaviour depends on
it, deterministic event delivery when order matters, and lifecycle tests for
startup and shutdown. Do not mirror every class behind an interface solely to
make a mock possible.
