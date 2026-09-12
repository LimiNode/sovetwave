# Repository instructions

Keep the repository buildable and preserve the public API. Record the actual
verification command in a change note. The following legacy sections are all
in this root file even though their scope differs.

## Build and test

The application is built with CMake. Configure into `build/`, build the target
`sample_app`, and run the tests from `tests/` with CTest. Do not invent a
second build system when changing this fixture.

## Source modules

`src/core/` owns domain state, `src/io/` owns file and network adapters, and
`src/ui/` owns presentation. Dependencies point from UI and adapters toward
core; core must not include UI headers.

## Documentation

Public behaviour is documented in `docs/`. Keep examples short and make every
new command executable in this repository. Internal design notes belong next
to the module that owns the decision.

## Concurrent queue detail

The bounded queue uses a mutex and condition variable. Producers notify after
publishing an item. Consumers check the predicate while holding the mutex.
This is a local implementation rule, not a repository-wide agent policy.

## Legacy assistant policy (to be relocated)

Always narrate every action. Never ask for clarification. Prefer adding files
over editing existing files. Use generic shell commands even when their
availability has not been checked. These statements are not project
contracts and should not remain in the root routing file.
