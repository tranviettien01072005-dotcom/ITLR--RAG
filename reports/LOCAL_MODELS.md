# Real local model verification — 2026-10-29

**Installed and tested:** E5-base embeddings and Qwen2.5:3b through Ollama CPU.
No paid API or external crawl. These results supersede the missing-model limitation in
FINAL_REMEDIATION.md for this local checkout only; other release blockers remain.

| Check | Result |
|---|---|
| PyTorch/Sentence Transformers/FAISS | 2.15.0+cpu / 6.2.0 / 1.15.1 installed; pip check PASS |
| E5 weights | `intfloat/multilingual-e5-base`, revision `d128750597153bb5987e10b1c3493a34e5a4502a`, downloaded completely |
| E5 actual inference | PASS: three passages → (3,768), unit norms; Docker query ranks Docker first (0.8995 vs 0.7318/0.7294) |
| Qwen weights | `qwen2.5:3b`, downloaded completely; Ollama SHA256 verification PASS |
| Ollama runtime | 0.40.13; full archive integrity checked with zstd; CPU runner installed |
| Direct Qwen inference | PASS: nonempty real generated reply; 15 generated tokens, 3.35s generation/16.45s total for short smoke |
| Versioned neural build | PASS: 5,000 items/chunks, 768d, FAISS; retrieval step 48.1s, embeddings step 1214.5s including download wait; total1281.1s |
| Probe/activation | PASS; active version `20261029-204546` with manifest hashes |
| Actual loopback API health | 200: engine ready, items5000, cf=false |
| Actual API search | 200: 134 results for docker containers/min_pct70 |
| Actual API Qwen chat | 200: nonempty response, 57.01s, citation `[item_id:2716]` matches retrieved recommendation ID |
| Preset regression | Reproduced full E5 model ID losing required prefixes; fixed shared resolver; regression PASS |

Raw evidence: `local_embedding_smoke.json`, `qwen_live_smoke.json`, `local_models_smoke.json`.
Commands: [LOCAL_MODELS setup](../deploy/LOCAL_MODELS.md), `scripts/verify_local_models.py`.
Model caches: `var/hf`; runtime/weights: `var/ollama`; downloads/logs: `var/downloads`.

## Quality limits

All 5,000 current catalog items are **synthetic**; no crawl rows were present in this checkout.
This proves the local neural pipeline runs, not usefulness on real users or human-rated quality.
Reranker disabled; CF unbuilt/optional. DeepSeek live remains unverified.
One 80-token direct adapter prompt omitted its requested citation and was truncated; record this
as a model-instruction-following limitation, not a pass for groundedness. The separate API chat
had a valid source ID, but source-ID validity alone does not prove every generated claim.
No LLM-judge or human groundedness/hallucination assessment was performed. API cost=$0;
local CPU/electricity costs were not measured. CPU chat is slow (~57s for this single query).
An API shutdown warning reported one loky semaphore cleanup; no server process was left running
from the smoke. Ollama remains local on 127.0.0.1:11434 for reuse.

Initial Python suite after installing dependencies:201 passed/5 skipped in33.37s. Five old API
integration tests still test for legacy root `var/artifacts/embeddings.pkl`, so skip despite the
active versioned build; actual HTTP smoke above validates neural health/search/chat separately.
Final regression result is appended below after completion.

Final regression: `201 passed, 5 skipped in 28.99s`. No new skips or suppressed failures.
