# ADR-011: Separate answer presentation and share the Web catalog contract

## Status

Implemented. The later Windows baseline completed 386 Python tests and 124 Web
tests; the original Linux-only collection blocker is historical. Linux lifecycle,
Docker/PostgreSQL staging and full production verification remain separate gates.
See [stream verification](../../reports/HARDENING_STREAM_2026-10-30.md).

## Date

2026-10-30

## Context

The 1516-line chatbot module combined retrieval/generation orchestration with
offline Markdown rendering, catalog facts and learning-path presentation. These
formatting helpers do not need an engine or provider client.

Web catalog sync accepted both legacy 10-column and provenance 16-column CSVs,
while community uploads always appended 10 fields. The resulting mixed-width CSV
could fail the next PostgreSQL COPY. The two writers/readers had separate schemas.

## Decision

Move the existing presentation definitions unchanged to `itlr/chatbot/presentation.py`.
Keep helper imports available from `chatbot.py`, along with EducationalChatbot,
intent routing, retrieval, provider adapters and citation enforcement. Do not add
a presenter class, factory, dependency container or second generation client.

Use `web/src/services/catalog-csv.ts` to read and whitelist CSV columns for both
dataset append and database sync. Close the stream in a finally block. Append all
columns in the current header, leaving unavailable provenance fields empty rather
than inventing source metadata. Reject missing/unsupported catalogs without writes.

Use the existing Python logger for LLM fallback failures. Remove redundant console
printing and exception suppression; preserve fallback return values and strict
stream error propagation.

## Consequences

Five template modes have before/after output fingerprints; the extracted 27
definitions were compared structurally before any other edit. Legacy import
paths remain available. The BM25 compatibility shim, V2 artifact branch, shared
retrieval service, API/schema and lifecycle protocol are unchanged.

CSV validation does not make PostgreSQL, catalog files and artifact activation one
transaction. Upload appends are still asynchronous at existing callers. ID allocation
remains process-local; external writers must be stopped during export/release work.
These constraints remain documented rather than hidden behind a new abstraction.

## Verification

See [the audit checkpoint](../../reports/ARCHITECTURE_REFACTOR_2026-10-30.md) for
RED/GREEN evidence, actual commands, benchmark scope and remaining release gates.

## Alternatives

Keeping presentation in chatbot.py retains mixed responsibilities; rewriting retrieval/provider logic together with presentation would expand compatibility risk. A shared CSV whitelist avoids separate append and COPY column definitions.
