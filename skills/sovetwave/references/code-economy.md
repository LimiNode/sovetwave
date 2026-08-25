# Code economy

Read this reference for code generation, modification, refactoring, or review in any programming language. Optimise for the smallest justified semantic surface, not for the fewest physical lines. Clear code may be longer than compressed code; the defect is unnecessary decisions, duplicated invariants, and structures without a current purpose.

## Before changing code

1. State the required observable behaviour and the relevant non-goals.
2. Inspect the existing implementation, callers, tests, and nearby helpers before adding a parallel path.
3. Reuse or extract shared logic only when the paths implement the same invariant. Similar syntax alone is not proof that one abstraction fits both.

For review, inspect both the changed code and its surrounding implementation. A locally correct diff can still leave an older path unused or add a second implementation of an existing helper.

## Review in two passes

First look for high-confidence local residue whose removal does not choose a new architecture:

- unused functions, lambdas, variables, branches, and intermediate states;
- conditions made constant by an earlier guard or loop exit;
- adjacent operations where the latter already subsumes the former;
- annotations, qualifiers, or comments contradicted by the implementation;
- an old implementation left beside the replacement.

Prove each finding from control flow, data flow, callers, or tool evidence. Do not classify code as dead from appearance alone.

Then search the repository for equivalent helpers, lifecycle wrappers, codecs, and test fixtures. Compare their contracts before proposing consolidation. Preserve real differences in ownership, rollback, compatibility, validation, and failure handling.

Use available compiler warnings and static analysis to inventory unused entities, constant conditions, redundant operations, and contradicted qualifiers in the reviewed scope. Search new helper names, signatures, and repeated operation sequences across the repository. Treat these results as leads and verify their semantics before reporting them.

When the user explicitly requests an anti-bloat or code-economy audit, keep confirmed semantic residue as a separate review pass. Higher-severity correctness findings do not replace it. Report the high-confidence residue within the requested result limit, or state that this pass found none; never invent findings to fill a quota.

## Keep the change bounded

- Prefer the smallest coherent change that satisfies the established requirement.
- Keep one source of truth for stable repeated behaviour. Do not copy a block into another handler, adapter, or test when the same contract already has an implementation.
- Remove an impossible branch, redundant flag, repeated computation, or dead intermediate state in the changed path when the precondition proving it is visible and tested.
- Do not add factories, registries, extension hooks, configuration switches, caching, retries, concurrency, or compatibility layers for hypothetical future requirements.
- Do not add a cache, registry, or new mutable state merely to repair code bloat. Require a measured cost or established requirement, compare a stateless or deletion-based correction first, and show that the result has fewer independent invariants.
- Treat annotations and qualifiers as contracts. Add `noexcept`, transactional guarantees, thread-safety claims, nullability promises, or similar declarations only when the implementation and failure paths satisfy them.
- Do not preserve a speculative abstraction merely because generated code already contains it. Existing complexity still needs a reason.

## Review the result

1. Enumerate the new semantic decisions: branches, states, ownership rules, error paths, and extension points. Remove those that are not required.
2. Search for duplicated or near-duplicated implementations whose later divergence would create multiple repair sites.
3. Use compiler warnings, static analysis, tests, and coverage as evidence for unreachable conditions and redundant states; do not delete a path from appearance alone.
4. Compare the patch with a simpler equivalent formulation. Prefer the version with fewer independent invariants while retaining readable names and explicit error handling.
5. Verify the requested behaviour and affected consumers. A smaller diff is not correct merely because it is smaller.

Report confirmed deletion and consolidation opportunities before speculative performance or architectural changes. For a large subsystem, propose staged seams only after identifying a concrete dependency boundary; do not prescribe a whole-system rewrite from file size or topic count.

Treat line count, token count, compilation time, and repeated analyzer warnings as diagnostic signals, not targets. The objective is code whose necessary behaviour is easy to locate, change, and verify.
