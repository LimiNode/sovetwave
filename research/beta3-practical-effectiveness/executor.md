# Executable fixture preflight

Status: trusted-control execution verified; live pilot HOLD. No model calls.

From the repository root:

```text
python research/beta3-practical-effectiveness/preflight.py --offline
python research/beta3-practical-effectiveness/preflight.py --build-image
python research/beta3-practical-effectiveness/preflight.py --selftest --image sha256:<returned-image-id> --output <new-report.json>
python research/beta3-practical-effectiveness/preflight.py --prepare state --output research/beta3-practical-effectiveness/executable/.temp/new-state
```

Provisioning may use the network to obtain the digest-pinned base and Debian
packages. Execution never does. Apt packages are not snapshot-pinned: rebuilds
need not have the same toolchain or image ID. Freeze the resulting immutable
image ID, content lock and reported compiler/CMake versions for a comparison;
never silently replace the image between arms. The observed image is recorded
in `runtime-preflight.json`. No automatic host-shell fallback exists.

Each fresh container has no host mounts, Docker socket, credentials, forwarded
environment or network; root is read-only. Only `/work` is writable tmpfs,
explicitly executable for compiled programs, with 256 MiB capacity. Limits are
512 MiB memory/no swap, one CPU, 64 processes, 64 MiB per file and no core dumps.
UID 65534, dropped capabilities, no-new-privileges and default seccomp apply.
Outer wall timeout is 90 seconds per task (two seconds for termination control),
with at most 2 MB collected stdout and bounded per-check diagnostics. Container
kill/removal occurs in the host-side finally path. No developer worktree is
deleted. Every case begins from an image fixture copy in a new tmpfs.

`content-lock.json` pins starter trees, trusted tests, reference implementations,
mutations, prompts and container entry point. `--prepare` creates a new synthetic
Git repository only beneath `executable/.temp`; existing destinations are
rejected, not reset. Fixed Git identity/dates and LF task bytes make its initial
commit reproducible. Reference and oracle files must never enter an agent's
generation workspace. Only the starter and exact prompt are agent inputs.

The control report records submitted/post-run file hashes, exact check IDs,
exit codes and diagnostics. A missing required check cannot yield PASS. The
`machine_gates` field maps required check IDs to functionality, completeness,
compatibility and safety statuses, limited to exercised contracts. Economy
remains NOT_ASSESSABLE; review becomes eligible only after those gates pass.
The boundary task additionally uses syscall evidence for a rejected traversal;
ASan/UBSan cover exercised paths only. The oracle permits alternative API-
compatible implementations, but greenfield layout checks intentionally test
the selected house profile. Directory markers establish layout, not actual
worktree creation or tool-use history. Brownfield protected-file checks establish
preservation, not helper reuse or historical scratch/build paths. Those properties
need semantic review and per-call traces before any observation is complete.

## Remaining trust boundary

This container protects the developer host under the tested Docker boundary;
it is not a VM or a proof against kernel exploits. The evaluator and submitted
program currently share a container UID. A deliberately adversarial candidate
could interfere with evaluator processes or inspect baked-in oracle/reference
files. Controls do not establish tamper-resistant grading. There is deliberately
no host-side candidate CLI or agent execution bridge yet. Before exposing
generated programs, review separation of trusted result collection from candidate
execution, hide reference solutions from generation, verify complete artifact
transfer, and prohibit direct host Bash execution. Keep HOLD until these and
the runtime/baseline-isolation bindings are closed.
