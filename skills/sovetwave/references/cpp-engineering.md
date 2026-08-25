# C++ engineering

Read this reference only for C or C++ code, reviews, diagnostics, portability, optimisation, ownership, or concurrency. It supplies an investigation order, not a substitute for the language standard, a compiler manual, or a reproducer. Do not quote or reproduce source material used to curate these principles.

## Establish the class of behaviour

Do not call every surprising C++ result undefined behaviour. Distinguish:

- undefined behaviour: the program violates a rule and the standard imposes no requirements on the result;
- unspecified behaviour: one of several permitted outcomes may occur without a required choice;
- implementation-defined behaviour: the implementation chooses and documents its behaviour.

Name a class only when the code and the applicable language/library rule establish it. Otherwise state the observation and the missing evidence. A successful build, a green test, or long production history does not establish that behaviour is defined by the standard.

## Inspect lifetime, validity, and ownership first

For a reference, pointer, iterator, view, range, proxy, capture, or coroutine handle, identify its owner and the last operation that can invalidate it. After a container mutation or an operation that can relocate storage, re-check values retained by callers and other abstraction layers; the local mutating function is not the only place where invalidation can surface.

For each resource-owning path, account for ownership before the call, after success, after every error return, and after an exception. Prefer an interface that makes this transfer explicit. Do not declare an error path safe merely because the normal path is covered by a test.

Do not infer a useful value from an object merely because it has been moved from. Establish what its type contract guarantees before reading it or reusing its contents.

## Inspect concurrent access as a whole

When state is shared, inspect all conflicting reads and writes, not only assignments. An apparently harmless observation of a non-atomic object can race with a write. Determine the synchronisation or atomic contract before proposing a lock, a memory order, or a waiting protocol.

## Use tools as evidence, not verdicts

Combine the smallest reproducer with compiler warnings, static analysis, sanitizers, and more than one relevant build configuration when practical. A sanitizer report is evidence of a defect; a clean sanitizer run covers only the executed path and does not prove the absence of every defect.

If a symptom changes between optimisation levels, compilers, standard libraries, or platforms, treat that as a discriminating clue. Do not call `-O0`, a particular compiler, or an added delay a repair until the violated rule or invariant has been repaired and checked under the required configuration.

## Keep C++ contracts and work justified

Treat `noexcept` as a behavioural contract, not decoration. Inspect allocation, container-capacity changes, user callbacks, and other potentially throwing operations before applying it. If failure may propagate, remove `noexcept`; if the interface must not throw, establish and test an explicit non-throwing failure policy. Do not add a catch-all merely to preserve the qualifier.

Use `reserve()` when an expected final or batch capacity is known. Repeating `reserve(size() + delta)` before every append can defeat geometric growth and turn an amortised operation into repeated relocation. Prefer normal container growth or one capacity reservation at the bulk-operation boundary, then verify the relevant workload.

After a guard or loop exit, re-evaluate conditions repeated inside or after that control-flow boundary. Remove a condition only when the path proves it constant; preserve superficially similar checks when a `break`, callback, or error transition can retain another state.
