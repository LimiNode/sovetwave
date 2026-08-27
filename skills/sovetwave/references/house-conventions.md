# Project and house conventions

Read this reference when generating or reviewing code whose naming,
lambda-capture, documentation, or local-style policy matters. Treat the house
profile below as an explicit fallback, not as a law of C++ and not as a reason
to rewrite a consistent repository.

## Resolve authority before style

Apply rules in this order:

1. language and standard-library contracts;
2. applicable repository instructions such as `AGENTS.md` and checked style
   guides;
3. the nearest established style in the owned subsystem;
4. an explicitly selected house profile;
5. otherwise, preserve the surrounding code and do not invent a convention.

Classify a finding as a language invariant, standard or library contract,
risk-reduction guideline, project convention, or author preference. A project
convention can be mandatory for that repository without becoming a correctness
rule elsewhere. If two instructions conflict, establish their scopes and
normative owner before changing code. Do not blend them into a third style.

## Make captures visible under the house profile

When the house profile is selected, do not use lambda default captures `[&]` or
`[=]`; list captures explicitly. Capture `this` explicitly when member access is
intended. This makes dependencies reviewable, but it does not prove lifetime or
thread safety. For a callback that can escape the current scope, still establish
the lifetime of every reference, pointer, and object reached through `this`.

Without the house profile or an equivalent repository rule, a default capture
is not inherently a defect. Review it according to the callback's lifetime,
mutation, concurrency, and the surrounding project's style. Recommend an
explicit list when it materially reduces risk or maintenance ambiguity; label
that recommendation accurately.

## Name by role and scope

Under the house profile:

- prefix private data members with `m_`;
- use predicates such as `m_is_...`, `m_has_...`, `m_use_...`, or
  `m_enable_...` for private boolean members;
- prefer names that expose representation, unit, encoding, coordinate space,
  or role when that distinction matters: `utf8_title`, `display_title`,
  `byte_count`, `row_index`;
- avoid Systems Hungarian prefixes such as `b_`, `n_`, or `f_` that merely
  repeat the declared type;
- treat `str_` and pointer prefixes as optional local conventions, not generic
  requirements. Use them only when the repository has adopted them and they add
  information beyond the type.

Do not impose one universal spelling for methods or free functions. Real
projects can consistently choose `camelCase` or `snake_case`; follow the
applicable repository contract. Preserve public API spelling unless the task
explicitly includes a compatibility-aware rename.

## Keep documentation policy local

Apply Doxygen marker, tag, and natural-language rules only when the repository
or selected profile establishes them. Under the house profile, use concise
technical English with `///` and backslash tags for public API documentation.
Do not add comments that restate syntax, and do not convert an unrelated change
into a documentation-style migration.

## Review the effect, not just the token

For a convention finding, cite the governing project rule or state that the
house profile was selected. Separate it from semantic defects. Verify a narrow
mechanical rule with a deterministic check where practical, but inspect the
code for meaning: an explicit capture list can still dangle, a well-prefixed
boolean can still encode impossible state, and consistent spelling can still
name the wrong abstraction.
