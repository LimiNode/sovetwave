# Changelog

## v0.5.0-beta.4 — 2026-11-12

- Added constructive C++ invariant guidance for state modeling, owner-thread
  versus intentionally shared state, and lifecycle-safe RAII registration
  tokens, including a conditional self-unsubscription teardown boundary.
- Made the hierarchical umbrella-based C++ profile explicit for independent
  translation units: an owning domain or subdomain umbrella comes first, with
  private leaves, brownfield exceptions, and standalone entry points kept
  within their documented contracts.
- Made the house profile the fallback for new projects without a competing
  style decision, including PascalCase classes, camelCase single-class file
  stems, and repository-local build, temporary, and worktree directories;
  added deliberate CMake target and shared data-domain guidance.
- Added focused offline coverage for C++ lifecycle, CMake target selection,
  naming, worktree, and umbrella-include conventions without claiming model
  quality or runtime enforcement from fixture counts.
- Kept benchmark research, host-enforcement adapters, and executable-oracle
  infrastructure outside the distributable production skill.

Limitations: no completed live A/B experiment or measured general improvement
in coding-agent performance is claimed for beta.4. No production-grade universal
Claude host enforcement is provided; research-only checks establish neither a
universal fail-closed boundary nor a security guarantee.

## v0.5.0-beta.3 — 2026-11-08

- Added evidence-bound architecture guidance that separates source entailment,
  authored models, and observed runtime impact.
- Added a deliberate C++ header dependency policy for new projects, including
  umbrella boundaries, private leaves, installed package consumers, and
  brownfield exceptions.
- Added optional task-contract and isolated `.worktrees` guidance for
  autonomous multi-stage changes and agent handoffs.
- Strengthened verification of executable documentation, specialized fast
  paths, benchmark semantic parity, mutation completeness, and declared
  compatibility boundaries.
- Expanded offline fixture and CI validation while keeping host enforcement
  adapters and research-only experiments outside the production skill.

## v0.5.0-beta.2 — 2026-09-20

- Added capability-aware inquiry and verification guidance for separating method fidelity from family-level representativeness, exposing residual information, and stopping investigation when a preregistered evidence boundary is met.
- Added contract-based tool-use guidance for purpose-built and typed tools, shell path boundaries, structured edits, and exit-status semantics.
- Added capability-stage metadata and repository-grounded tool-use fixtures to make evaluation coverage and operational assumptions explicit.
- Added the frozen integral beta.2 evaluation manifest and supporting documentation for reproducible baseline/Sovetwave comparisons.
- GitHub-hosted CI validates the repository validators, behavioral harness, and installer smoke checks; the full local validation suite includes additional release and pytest checks.

## v0.5.0-beta.1 — 2026-09-15

- Replaced runtime voice-card selection with deterministic static scene/domain routing, preserving the validated card corpus without a tool round-trip.
- Added project-documentation guidance for contracts, ADRs, plans, research notes, runbooks, documentation drift, and proportional change impact.
- Added behavioral coverage for documentation ownership, epistemic status facets, lifecycle, and public API documentation impact.
- Expanded low-risk technical humour with provenance-aware transform-only patterns and bounded original asides while preserving literal language in critical contexts.
- Updated the public README and Claude plugin metadata for the current beta package.
- GitHub-hosted CI was unavailable because of account billing restrictions; local validation and installer smoke checks were run for this release candidate.

## v0.4.0 — 2026-08-11

- Hardened behavioral rules for evidence-based diagnosis: static defects, delivery guarantees, and API shapes now remain conditional when the project contract is unknown.
- Added regression fixtures for silent activation, causal calibration, queue delivery semantics, local lifetime verification, and choosing an empty-result API only after the contract is known.
- Refined the low-risk engineering voice with short, original causal observations while retaining literal language for critical contexts.

## v0.3.0 — 2026-08-07

- Added the engineering core: fact, mechanism, action, and verification.
- Added a curated scene-based voice corpus with provenance, safety boundaries, and deterministic selection.
- Added native Russian technical prose, preserving formal identifiers while avoiding needless English-language calques.
- Added Codex and Claude installation paths, cross-platform installer smoke tests, eval-fixture validation, and CI.

## Release policy

Use semantic version tags for distributable releases. Record user-visible changes here; keep research notes and internal curation history out of release notes.
