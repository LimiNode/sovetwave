# Python engineering

Read this reference for Python code, reviews, diagnostics, packaging, or
concurrency. Establish only the Python version, implementation, toolchain,
packaging, concurrency, lifecycle, or execution facts that can materially
change the recommendation or its verification. For a local language-level
defect, do not block analysis on unrelated project metadata. Before executing
a command, establish its actual entry point and working directory. Preserve
repository evidence instead of replacing its toolchain with a preferred
framework.

## Keep ownership visible

Use context managers for resources whose acquisition and release form one
scope: files, locks, transactions, temporary directories, sockets, and
project-specific sessions. Prefer an existing context-manager API over a
manually duplicated `try/finally`. When no such API exists, put cleanup in a
`finally` block or provide a small owning abstraction. Establish whether a
returned iterator, generator, callback, or task outlives the resource it uses.

Do not infer safety merely from garbage collection or CPython reference
counting. Prompt release and behaviour on another Python implementation require
an explicit contract. Verify partial acquisition and every exception path, not
only the successful body.

## Draw exception boundaries deliberately

Catch the narrow exceptions that the current boundary can handle. Preserve the
original exception with chaining when translating it into a domain error.
Avoid `except:` and broad `except Exception:` blocks that log and continue
without restoring an invariant. A top-level command, worker, or request
boundary can catch broadly to record failure, but it still needs a defined
exit, retry, or response contract.

Do not use exceptions as evidence that partially completed external work was
rolled back. Establish transaction, idempotency, and cleanup behaviour
separately. Do not add retries without a classified transient failure,
bounded policy, and observability.

## Avoid shared defaults and hidden state

Default argument expressions are evaluated when the function is defined. Do
not use a mutable object as a default when calls require independent state.
Use a sentinel such as `None` and create the object inside the function, unless
shared state is the explicit documented contract.

Apply the same scrutiny to module globals, class attributes, caches, closures,
and decorators. A convenient object with process lifetime is shared state; it
needs ownership, reset, concurrency, and test-isolation semantics.

## Treat typing as an interface, not a guard

Type annotations help tools and readers describe an interface, but Python does
not generally enforce them at runtime. Validate and normalize data at untrusted
boundaries according to the actual schema. Do not duplicate runtime validation
through every internal layer once the boundary has established a trusted
representation.

Preserve public annotations and compatibility in a library. Establish the
configured type checker and its mode before claiming a type-check result.
Avoid a large typing abstraction that exists only to satisfy one local
expression; prefer a small protocol, type alias, or direct annotation when it
matches an established interface.

## Respect packaging and import boundaries

Declare runtime dependencies in the project's packaging metadata and
development-only tools in the appropriate optional or development group.
Do not make an undeclared transitive dependency part of the program's contract.
Preserve the repository's chosen build backend, environment manager, package
layout, and supported versions unless the task explicitly includes migration.

Use imports that match the installed package boundary. Do not repair an import
by mutating `sys.path` in application code when the real issue is invocation,
layout, or missing package metadata. Keep optional dependencies behind an
explicit feature boundary with an actionable failure; do not silently disable
required behaviour after `ImportError`.

## Own asynchronous work and cancellation

Every created task needs an owner that awaits it, keeps it alive for a defined
period, or supervises and reports its failure. Prefer structured concurrency
facilities available in the established Python version. Do not launch a task
and discard the handle merely to make work concurrent.

Cancellation is part of an asynchronous function's control flow. Use
`try/finally` to release resources and normally allow cancellation to
propagate. Catch cancellation only when the boundary has a specific contract,
and re-raise it after cleanup unless deliberate suppression is documented.
Define shutdown: stop accepting work, signal owned tasks, await their cleanup,
and bound the wait when the application requires a deadline.

Choose `asyncio` for cooperative asynchronous I/O only when dependencies expose
compatible non-blocking operations. Move a blocking call away from the event
loop deliberately. For CPU-bound parallelism, first establish the Python
implementation and version, whether the runtime has an enabled GIL, and whether
native extensions support the selected mode. In GIL-enabled CPython, processes
or native code that releases the GIL often fit measured CPU-bound work; in a
free-threaded CPython build, threads may also execute Python code in parallel.
Choose from measured workload, shared-state safety, data-transfer cost, startup,
and deployment constraints. Do not introduce an async framework, worker pool,
or task queue without an established workload and lifecycle.

## Verify the actual boundary

Run the project's formatter, linter, type checker, tests, and packaging checks
only when they are configured; record unavailable checks as not run. Add a
focused test for the failure mechanism: two calls for a mutable default,
injected acquisition failure for cleanup, invalid external data for runtime
validation, cancelled tasks for shutdown, or a clean environment for declared
dependencies. A passing type check does not prove runtime data, and a passing
unit test does not prove packaging from a clean installation.
