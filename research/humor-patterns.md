# Humor pattern audit

This is a provenance-aware pattern inventory, not a quotation bank. The local
working corpus in `temp/` contains mixed material: scientific humour, teacher
collections, engineering transcripts, memoirs, and meme fragments. Only the
source classes and reusable mechanisms below are carried into the skill; raw
texts remain outside the distributable package.

## Extraction rule

For each candidate, record the technical tension and the reusable move, then
write an original anchor. Do not copy a sentence, preserve an uncertain
attribution, or present a source anecdote as a project fact. The card remains
`transform_only` unless the source and attribution are established for an
anonymous style anchor.

## Current patterns

| Pattern | Technical tension | Reusable move | Source class | Card |
| --- | --- | --- | --- | --- |
| test proves a neighbour property | green test versus unexercised behaviour | praise the property that was actually measured, then name the gap | teacher collection | `humor-test-neighbor-property` |
| retry without idempotency | more attempts versus multiplied side effects | take “retry” literally, then require idempotency | professional folklore | `humor-repeat-without-idempotency` |
| cache without freshness | faster lookup versus stale state | praise speed while exposing the missing invalidation | engineering transcript | `humor-fast-stale-cache` |
| abstraction before a second use | promised reuse versus one concrete call | treat premature scale as an observable mismatch | research/engineering anecdote | `humor-scale-before-second-use` |
| interface hides detail in a signature | encapsulation claim versus caller-visible complexity | praise the wrong property literally, then simplify the contract | computing memoir/history | `humor-details-in-signature` |

These patterns are allowed only for one low-risk explanatory aside. They are
not used in safety, security, incidents, migrations, destructive operations,
public release prose, or other literal-language contexts.
