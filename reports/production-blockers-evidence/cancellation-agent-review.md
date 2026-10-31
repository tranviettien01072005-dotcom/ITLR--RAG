# Cancellation reproduction and async-path review

Scope: agent changed only `tests/test_stream_cancellation.py`; parent owns all application fixes. No cloud calls, model inference, commits, Docker or existing services were used by this agent.

## Reproduction and regression

- `cancellation-red.log`: original application, two tests FAIL (10.57s). Before-first-delta disconnect waits for the 3s provider read timeout; after-first-delta disconnect returns but provider TCP socket remains open while the API response is retained.
- `cancellation-regression-before.log`: original cancellation behavior, two FAIL and one PASS (15.32s). Existing timeout already replaces a partial draft with a single failure final/done; that contract was preserved, not claimed as a newly fixed bug.
- `async-utf8-red.log`: first async implementation, two FAIL and one PASS (1.81s). `httpx.aiter_lines()` replaces corrupt UTF-8, accepting both invalid FF and truncated E2 82 in JSON text. A valid Vietnamese string split into byte-sized HTTP chunks passes.
- `cancellation-agent-green.log`: final application path, **7 PASS** (6.72s), no skip. Covers disconnect before first delta and after first delta; total provider timeout with partial output; two corrupt UTF-8 cases; valid fragmented UTF-8; ASGI2.4 send OSError after sources with retained response and suspended engine-generator finally.

The provider is a real loopback TCP HTTP/1.1 chunked server. Cancellation tests require API response termination under 1s after disconnect (provider timeout is 3s), provider-side EOF/RST within 0.5s, and no final/done after disconnect. Preparation is a deterministic fixture to avoid loading E5; ASGI response is invoked directly to control receive/send precisely. These are provider-socket transport regressions, not actual Ollama inference or a full Browser/Express/Uvicorn journey.

## Fresh read-only application review

No new local-path defect found in the reviewed async chain. Async adapter/engine/chatbot wrappers explicitly close nested iterators. CancelledError is not swallowed by Exception fallback handlers. ClosingStreamingResponse closes a generator suspended during ASGI send failure under a shielded cleanup scope. Ollama async I/O has a total deadline, closes client/response context managers, preserves completion metadata checks, and now uses strict incremental UTF-8 decoding across byte chunks. Existing sync public methods remain available.

Limits: preparation/probe worker-thread CPU work cannot be forcibly interrupted; it must finish independently, though no provider generation need start after cancellation. Provider probe is outside the async total generation deadline, so the budget is not a strict end-to-end request deadline. Legacy engines that only expose sync chat_stream still use a threadpool fallback with weaker blocking-read cancellation guarantees; actual current V2/V3 RecommenderEngine exposes the async method. Cloud async compatibility code was source-reviewed only; no cloud requests were made. Context/token correctness, real Ollama cancellation and full browser-to-provider resource release require the parent's separate runtime evidence.
