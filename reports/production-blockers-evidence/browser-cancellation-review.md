# Real browser-to-Ollama cancellation verification

Fresh full-chain runtime: real Chrome UI → Express18030 → new FastAPI18080 → transparent observation proxy18435 → actual Ollama11434 `qwen2.5:3b`. API loaded trusted real E5-base768d staging (118 items/1576 chunks); API provider budget45s. PostgreSQL18 reused the isolated fixture cluster without migration/seed. Existing user services8000/4173/11434 were left running.

The proxy forwards actual request/response bytes and records only model/stream flag, prompt character count, body hash/size, byte counts and monotonic lifecycle timestamps. It does not synthesize model output or record prompt text, auth/session headers, passwords or keys. Generation prompt5811 characters, num_predict2000, known cached DEV404 question. This tests cancellation, not independent generation faithfulness.

## Successful browser cases

| Case | Real draft chars at Stop | UI ready after Stop | Actual Ollama socket closed after Stop | DB messages | Next actual model probe |
|---|---:|---:|---:|---|---:|
| Before first delta | 0 | 0.03070s | 0.06384s | user3/assistant3 unchanged | 0.32710s, `OK`, done/stop |
| After first delta | 4 | 0.02096s | 0.07716s | user3/assistant3 unchanged | 0.31078s, `OK`, done/stop |

Both used the actual Stop button. Both cleared the provisional answer, left conversation ID empty and URL `/chat`, and displayed the cancellation status. Proxy saw API client EOF and closed its real11434 socket before terminal completion; no provider `done=true` was observed. Browser runtime exceptions: none. No user or assistant message was persisted by these aborted requests.

The next tiny real Qwen request after each abort completed in ~0.3s, demonstrating prompt service availability rather than waiting for a full abandoned response. This is not proof that every backend decode operation stopped immediately: the shared llama-server CPU measured218.5%/202.9% across1s windows, and no per-request backend cancellation ACK is exposed. Do not claim zero CPU usage, model-internal compute release, global queue emptiness or capacity/soak from these two samples.

## Harness history and scope limits

Two initial harness attempts failed before the final successful run. One synthetic mouse click did not scroll the Stop button into view after sources expanded the page; Chrome termination then closed the stream. A later attempt hit a navigation/node-ID race before submitting a model request. Those logs are preserved as `browser-cancellation-first-harness-failure.log` and `browser-cancellation-navigation-harness-failure.log`. The harness now waits for document completion, retries stale node IDs and scrolls targets into view before real mouse events. These were harness defects, not application RED evidence, and were not counted as successful Stop cases.

Use the separate `cancellation-red.log` and `async-utf8-red.log` for application FAIL→fix→PASS evidence. This successful full-chain run uses a cached known query, not a cold/full-blind-prompt latency benchmark. It makes no human grounding/faithfulness claim.

## Cleanup and review

`cancel-cleanup.json` confirms ports15432/18030/18080/18435 closed, fixture data preserved, no migration/seed. Own Chrome was terminated by the harness. No further application defect was found during this integration. Parent owns application source fixes; this agent made no additional application edits.

Copyable artifacts: `browser-cancellation.json`, `browser-cancellation.log`, `cancellation-proxy.json`, `browser_cancellation.py`, `cancellation_proxy.py`, `start_cancellation_services.py`, `cleanup_cancellation_services.py`, `cancel-cleanup.json`, `cancel-api.log`, and this summary. Do not copy private env/state, database data, Chrome profiles or session storage.
