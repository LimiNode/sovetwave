# Executable oracle vertical slice

This is the first small evidence-grade execution path for the next coding-agent
experiment. It uses the existing `validate_applicable_axes(value, *, allowed)`
contract as a concrete task and runs an independent oracle against four
trusted, checked-in reference implementations:

- one correct implementation;
- one that accepts duplicate axes;
- one that accepts unknown axes;
- one that rejects the optional `None` value.

The oracle executes seven fixed inputs covering optional, normal, boundary, and
rejection groups. It reports per-case observations, an independent correctness
verdict, a completeness verdict, and source/oracle provenance. The expected
outcome is defined by `task.json`, not by a candidate's self-report.

The pinned repository contract is checked with `git show`, SHA-256, and a source
marker at revision `a188183c16a424ef3848458dadb0df3858eb48fa`. The current
checkout identity is recorded separately. The trusted helper implementations
run in-process; this is deliberately not a sandbox for model-generated code.
`generated_code_executed=false` is an execution boundary, not a claim that a
filesystem or host guard was observed. A future agent experiment needs a
separately reviewed isolation boundary before candidate code may be executed.

Run the deterministic oracle without model calls:

```text
python research/executable-oracle/oracle.py --selftest
python tests/behavioral/test_executable_oracle.py
```

The production skill, beta.2 artifacts, and historical grading are not part of
this PR.
