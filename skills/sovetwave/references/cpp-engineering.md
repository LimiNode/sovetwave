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

## Match mutable state scope to object identity

When an instance method exposes a mutable reference or pointer, identify the
storage behind it. A function-local `static` object is shared by every call to
that implementation, including calls through different instances. Thread-safe
initialization of the local static does not provide per-instance isolation or
synchronize later mutation.

If the contract requires one callback, registry entry, cache, or status slot per
object, keep that state in the object or in external storage keyed by a stable
instance identity. Use shared static state only when sharing is the established
contract. Verify isolation with at least two instances: assigning or clearing
one slot must not change the other.

Preserve sentinel semantics. An empty `std::function` can represent an
unclaimed callback slot because its boolean conversion is false; a no-op lambda
is an installed callable and is therefore not equivalent. Moving a slot into an
instance also ties destruction of the callable to that instance, but it does
not establish the lifetime of objects reached through the callback, the owner
that assigns it, or pending operations. Check those contracts separately.

For associative insertion, keep the operation contracts distinct. With
`try_emplace`, mapped-value rvalue arguments are not moved from when insertion
does not occur because the equivalent key already exists. Do not transfer
that guarantee to `emplace`: it may construct a candidate mapped value and
may move a supplied rvalue before discovering that no insertion is needed.
Argument expressions are evaluated before either function call, so this rule
does not make construction of the call arguments lazy.

## Inspect concurrent access as a whole

When state is shared, inspect all conflicting reads and writes, not only assignments. An apparently harmless observation of a non-atomic object can race with a write. Determine the synchronisation or atomic contract before proposing a lock, a memory order, or a waiting protocol.

## Choose the C++ header dependency topology deliberately

For a **new C++ library or project**, propose **hierarchical umbrella-based
dependencies** as the default architecture. This is a project-level policy,
not a C++ language rule or a reason to migrate an existing coherent codebase.
At the initial architecture decision, briefly state the default and offer
two alternatives: independently self-contained headers (Include What You Use)
and a hybrid with standalone public/optional modules. Respect the user's
explicit choice and local repository instructions. If the user has delegated
the layout choice, use the default without repeatedly asking; for brownfield
work, preserve the existing dependency model unless a concrete requirement
justifies changing it.

Under the hierarchical umbrella default:

- **Declare include entry points.** Provide a self-contained umbrella for each
  domain; add subdomain umbrellas when they establish a useful boundary, not
  merely for symmetry. A library-wide umbrella is optional and exposes the
  intended public API, not every private detail or optional backend.
- **Centralize domain dependencies.** Each domain umbrella explicitly includes
  the lower-level domain umbrellas or narrower lower-level contracts it needs,
  followed by its own headers in a deliberate, deterministic order. The
  umbrella documents the domain's required dependencies in one place.
- **Keep the domain graph acyclic.** Shared lower-level dependencies are valid:
  the graph is a DAG, not necessarily a tree. Never introduce an upward
  dependency from a lower layer to its consumer or include the root umbrella
  from internal leaf headers. Resolve reverse dependencies through a smaller
  lower-level contract, a valid forward declaration, or a revised domain
  boundary; an extra umbrella does not itself eliminate a cycle.
- **Distinguish private leaves from entry points.** A private leaf header may
  rely on declarations provided by its domain umbrella and need not compile
  when included independently. Do not expose or include such leaves directly
  from another domain, external consumer, or translation unit that has not
  established the domain context. Implementation `.cpp` files that rely on
  that context include their domain umbrella first. In header-only projects,
  also verify include order, ODR correctness, and platform-header sequencing.
- **Make exceptions explicit.** Independently usable headers (for example,
  optional modules, plugins, or widgets) are self-contained include entry
  points. Prefer a coherent independently usable domain where practical.
  Document each such exception and its supported include path in project
  architecture documentation **and** in the header's Doxygen comments;
  follow the repository's Doxygen syntax and language conventions.
- **Use unambiguous include paths.** For new projects, prefer quoted local
  paths inside a domain and include-root-qualified paths such as
  `<library/core/types.hpp>` across domain boundaries. Prefer `/` separators
  and disallow `..` traversal as an explicit project convention; these paths
  are relative to configured include roots, not absolute filesystem paths.

**Verify the promised boundary, not an invented one.** Compile each declared
umbrella and standalone header as the first include in a clean translation
unit, check the domain dependency graph and required build configurations,
and test an installed consumer when installation is part of the contract.
Do not impose individual include-self-containment tests on private leaves
that are not independent entry points. An umbrella may increase parsing and
rebuild scope; measure that cost before claiming a performance advantage.
## Repository and package boundaries

When a C++ project exposes a reusable library or CMake package, treat the
installed interface and dependency ownership as part of its contract. A green
build from the source tree does not prove that a clean consumer can include
the public headers, resolve exported targets, link required transitive
dependencies, and use the declared language standard. Verify those properties
from the installed package when the project claims them.

Source layout, build-directory names, and the presence of a preset file are
repository conventions rather than universal C++ rules. Preserve an existing
layout unless the public interface, build reproducibility, or maintenance
contract gives a concrete reason to change it. Likewise, dependency folders
or submodules do not establish ownership by their physical presence; identify
the acquisition mechanism, pinned version, and target boundary explicitly.

## Use tools as evidence, not verdicts

Combine the smallest reproducer with compiler warnings, static analysis, sanitizers, and more than one relevant build configuration when practical. A sanitizer report is evidence of a defect; a clean sanitizer run covers only the executed path and does not prove the absence of every defect.

If a symptom changes between optimisation levels, compilers, standard libraries, or platforms, treat that as a discriminating clue. Do not call `-O0`, a particular compiler, or an added delay a repair until the violated rule or invariant has been repaired and checked under the required configuration.

## Keep C++ contracts and work justified

Treat `noexcept` as a behavioural contract, not decoration. Inspect allocation, container-capacity changes, user callbacks, and other potentially throwing operations before applying it. If failure may propagate, remove `noexcept`; if the interface must not throw, establish and test an explicit non-throwing failure policy. Do not add a catch-all merely to preserve the qualifier.

Use `reserve()` when an expected final or batch capacity is known. Repeating `reserve(size() + delta)` before every append can defeat geometric growth and turn an amortised operation into repeated relocation. Prefer normal container growth or one capacity reservation at the bulk-operation boundary, then verify the relevant workload.

After a guard or loop exit, re-evaluate conditions repeated inside or after that control-flow boundary. Remove a condition only when the path proves it constant; preserve superficially similar checks when a `break`, callback, or error transition can retain another state.
