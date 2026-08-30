# C engineering

Read this reference only for C code or a C-facing interface. Establish the C
standard and implementation, then only the target constraints that can
materially change the recommendation: storage limits, stack budget, concurrency,
reentrancy, and the selected safety profile. When a missing constraint affects
only one branch of the answer, state that branch conditionally instead of
blocking the analysis. A rule from an embedded or high-assurance profile is
evidence for a tradeoff, not an automatic requirement for a general-purpose
program.

## Classify the rule before enforcing it

Separate these categories in reviews and recommendations:

- a language constraint whose violation requires a diagnostic, or a language
  precondition whose violation produces undefined behaviour;
- implementation-defined or unspecified behaviour whose acceptability depends
  on the established implementation and portability requirements;
- a risk-reduction guideline that trades flexibility for simpler reasoning;
- a safety or certification profile selected by the project;
- a repository convention or author preference.

Report the first two according to the established C and portability contracts.
Apply the remaining categories only when the project adopts them or when their
tradeoff fits the stated goal. Do not call a policy violation undefined
behaviour, and do not call a permitted implementation choice a violation.

## Choose storage duration deliberately

For a small temporary object with a compile-time upper bound and lifetime equal
to one call, prefer a fixed-size object with automatic storage duration over an
otherwise unnecessary allocation/release pair when the stack budget is known to
be adequate. In ordinary implementations this is commonly stack-backed, but the
C language contract is automatic storage duration, not a particular physical
stack.

Do not generalise this into “heap allocation is forbidden”. Avoid or redesign an
automatic object when its size is large, controlled by input, multiplied by
recursion depth, or incompatible with the target's stack budget. Treat a VLA
whose bound is untrusted or insufficiently capped as a resource and bounds risk.
For variable, large, long-lived, or externally owned data, choose storage from
the established lifetime and resource model: caller-provided or context-owned
storage, an arena or pool, explicit dynamic allocation, bounded automatic
storage or a permitted VLA, or static-duration state when persistence and
sharing are intentional. These are contracts, not a universal preference order.

A function-local `static` array has program lifetime and shared state across
calls. It is not a substitute for an automatic temporary buffer. Use it only
when persistent shared state is intended and reentrancy, recursion, concurrent
access, initialization, and reset semantics are established.

When an API returns a borrowed pointer into mutable shared static storage, a
lock held only while filling the buffer does not protect the caller's later use.
Prefer caller-owned, per-call, or per-instance storage. Accept synchronized
shared scratch only when the contract prevents overwrite for the caller's whole
borrowing lifetime and also addresses recursion.

## Keep allocation and release in one ownership abstraction

When dynamic storage is justified, make the owning component and release path
visible. Prefer allocation and release at the same abstraction level or behind
paired module functions. Verify every early return, partial initialization, and
failure branch; a cleanup label can be clearer than duplicated cleanup when it
preserves one reverse construction order.

Before allocating `count * element_size`, prove that the multiplication fits
`size_t` and that the requested size satisfies the API and project limits. Keep
the original pointer until `realloc` succeeds; assigning its result directly to
the sole owner can lose the allocation on failure. Initialize ownership state so
that cleanup is valid after every partially completed step.

## Carry bounds with pointers

An array parameter is adjusted to a pointer in a function declaration. Do not
derive the caller's array length with `sizeof` on that parameter. Pass capacity,
used length, and element size where the callee needs them, and keep their units
unambiguous. Account for terminators and sentinels separately from payload
length.

Validate signed-to-unsigned conversions, narrowing, additions, multiplications,
and index calculations before pointer arithmetic, allocation, copying, or loop
bounds. A successful allocation does not prove that the preceding size
calculation was valid.

## Make failure paths observable

Define whether a function leaves outputs unchanged, resets them, or transfers
partial ownership on failure. Check return values before using outputs. Do not
hide a resource failure behind a generic success value or leave a caller to
guess whether cleanup is required.

Verify the narrow property with compiler warnings and the project's static
analysis first. Use ASan/UBSan or platform equivalents for reachable memory and
undefined-behaviour paths. For allocation-size arithmetic and other defined
unsigned wrapping, use explicit checked arithmetic, static analysis, and
boundary tests rather than relying on sanitizers alone. Use constrained-stack,
recursion, fuzz, or concurrency tests when those conditions are part of the
risk. Tool output is evidence about the exercised path, not proof of all call
patterns or target limits.
