# Fixture contract status

The six JSON files specify repository shape, required behaviour, negative
controls, and oracle boundaries. Each now binds an executable starter and
reference tree through `executable_fixture`. They contain no model-generated
code and are not model evaluation results. Checks derived from the common task
prompt are graded as engineering gates; Sovetwave conventions are reported
under `policy_adherence`. Freeze their content lock before
authorizing any live run; do not revise requirements after inspecting results.

Trusted reference/mutant/starter controls validate the bounded oracles. Before
a live run, the agent bridge and arm isolation still require review. Every
model observation remains `NOT_EXECUTED`; controls do not establish model
quality. Semantic constraints not exercised by an oracle remain
`NOT_ASSESSABLE`, never an inferred PASS.
