# Experimental minimal-solution ladder

This overlay is research input for one comparison arm. It is not part of the
production Sovetwave skill.

Before adding a new implementation, record the observable contract and check
the following in order:

1. Is the requested behaviour required by the task, including its negative
   and error cases?
2. Does the repository already contain a helper or implementation with the
   required contract?
3. Can the standard library or platform provide that contract without a new
   project abstraction?
4. Does an already approved dependency provide it without weakening the
   required validation or failure behaviour?
5. Only then design the smallest new implementation that preserves the
   contract and its checks.

This ordering is an experimental treatment of the hypothesis recorded in the
external-tools adoption review. It does not authorize skipping safety,
validation, error handling, or required tests.
