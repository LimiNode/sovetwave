# Fixture contract status

The six JSON files in this directory are immutable task contracts for the
offline design review. They specify the repository shape, required behaviour,
negative controls, and the oracle boundary. They deliberately do not contain
model-generated code and are not an execution result.

Before a live run, a separate preflight must bind each contract to a reviewed
synthetic repository (or a pinned real fixture), implement and test its oracle,
and record the fixture hashes. Until then, every proposed observation for that
task is `NOT_EXECUTED` or `NOT_ASSESSABLE`.
