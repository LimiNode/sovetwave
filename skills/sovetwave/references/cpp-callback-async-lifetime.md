# C++ callback and asynchronous lifetime discipline

Use this reference when C++ code calls callbacks, virtual or plugin code around
locks, or when asynchronous handlers can extend object lifetime or participate
in shutdown.

## Call out after releasing the lock

A callback, virtual dispatch, plugin hook, logging hook, or external operation
may synchronously re-enter the object, block, destroy it, or acquire another
lock. Treat such code as unknown unless an explicit contract proves otherwise.

Normally perform the protected state transition or take an owned snapshot
while holding the lock, release the lock, and then call out. Verify the
reentrant path, such as `on_data() -> stop()`, rather than only the ordinary
return path.

Do not unlock mechanically when the invariant requires an atomic reservation
or prevents another operation from observing an intermediate state. Represent
that boundary explicitly with a two-phase state, token, queue entry, or other
owned hand-off, then call out after the protected phase.

Do not introduce `recursive_mutex` merely to make accidental reentrancy
complete. It may remove the immediate self-deadlock while exposing a
half-updated invariant to the callback. Establish whether reentrancy is part of
the object contract first.

## Separate asynchronous ownership

Establish these properties independently:

- object lifetime;
- operation lifetime;
- buffer and resource lifetime;
- cancellation and stop semantics;
- callback execution context.

Capturing `shared_from_this()` in a pending finite operation can validly keep
the object and its buffers alive until completion. Do not report that pattern
as a leak or an anti-pattern without the surrounding lifecycle contract.

A strong self-reference also makes the operation an owner. Resetting the last
external `shared_ptr` is therefore not cancellation while pending handlers
retain the object. For a long-running or self-renewing chain, establish an
explicit stop or cancel event and the point after which handlers stop
propagating strong ownership. Distinguish memory that is never released from an
object released later than the caller's stop contract permits.

## Design teardown from every execution context

The last strong reference can disappear inside a handler, so a destructor may
run on the worker or callback thread. Trace shutdown from each context that can
release ownership.

Joining the current thread is invalid and may report
`resource_deadlock_would_occur`. Do not add a thread-id branch or detach as a
reflex: first assign teardown coordination and thread joining to an owner that
can execute them from a valid context. Use two-phase shutdown when stopping
work and reclaiming its owner cannot safely occur in one callback.

Never join, wait, or synchronously drain work while holding a lock that the
worker, completion handler, or cancellation path may need. Snapshot or mark
shutdown under the lock, release it, then signal, cancel, drain, or join in the
established order.

## Verify liveness boundaries

Select checks from the established contract:

- a callback synchronously re-enters the object;
- the last external or internal owner disappears inside a callback;
- cancellation occurs with a handler pending and a late completion arrives;
- a finite operation completes and releases its final strong ownership;
- teardown is reached from the owned worker thread;
- awaited work requires the same lock held by the waiter.

A sanitizer can support lifetime evidence for executed paths, but it does not
prove absence of deadlock, completion, or correct cancellation semantics.
