# ITLR–RAG | Intelligent IT Learning Platform

## Local neural model verification

Historical record: 2026-10-29. This document describes evidence and decisions at that checkpoint. See the [current platform guide](../README.md) and [current validation](VALIDATION.md) for later changes and runtime status.

E5-base embeddings and Qwen2.5:3b were installed and exercised through Ollama CPU. No paid API call or external crawl occurred. This superseded the missing-model limitation in [FINAL_REMEDIATION.md](FINAL_REMEDIATION.md) for the measured local checkout; other release gates remained.

| Check | Recorded result |
|---|---|
| PyTorch / Sentence Transformers / FAISS | 2.15.0+cpu / 6.2.0 / 1.15.1; `pip check` passed |
| E5 weights | `intfloat/multilingual-e5-base`, complete revision `d128750597153bb5987e10b1c3493a34e5a4502a` |
| E5 inference | Three passages produced `(3,768)` unit-normalized vectors; Docker query ranked Docker first, 0.8995 versus 0.7318/0.7294 |
| Qwen weights | Complete `qwen2.5:3b`; Ollama SHA256 verification passed |
| Ollama | 0.40.13; full archive integrity checked using zstd, CPU runner installed |
| Direct Qwen inference | Nonempty generated reply; 15 tokens, 3.35s generation and 16.45s total |
| Versioned neural build | 5,000 items/chunks, 768d, FAISS; retrieval 48.1s, embeddings 1214.5s including download wait, total 1281.1s |
| Probe/activation | Passed; version `20261029-204546`, manifest hashes recorded |
| Loopback health | HTTP 200, engine ready, `items=5000`, `cf=false` |
| API search | HTTP 200, 134 results for docker containers / `min_pct=70` |
| API Qwen chat | HTTP 200, nonempty answer in 57.01s; `[item_id:2716]` matched a retrieved recommendation |
| E5 preset regression | Full model ID lost query/passage prefixes before shared resolver correction; regression passed after correction |

Raw evidence: `local_embedding_smoke.json`, `qwen_live_smoke.json`, `local_models_smoke.json`. Reproduction uses `scripts/verify_local_models.py` and the [local model setup](../deploy/LOCAL_MODELS.md). Caches were under `var/hf`; Ollama runtime/weights under `var/ollama`; downloads/logs under `var/downloads`.

### Interpretation and limits

The catalog at this checkpoint contained 5,000 synthetic items and no crawl rows. The checks establish local pipeline execution, without measuring usefulness or human-rated quality. Reranking was disabled, CF unbuilt/optional and live DeepSeek unverified.

A separate direct adapter prompt, limited to 80 tokens, omitted the requested citation and was truncated. This is an instruction-following limitation. The API answer contained a valid retrieved ID, but ID validity does not establish claim entailment, groundedness or hallucination rate. No human or LLM-judge assessment was performed. API cost was $0; local electricity/CPU costs were unmeasured. One query took roughly 57s, without a throughput claim.

Shutdown emitted one loky semaphore cleanup warning; the smoke server was stopped. Ollama remained on `127.0.0.1:11434` for reuse. Initial Python regression: 201 passed / 5 skipped in 33.37s; final regression: 201 passed / 5 skipped in 28.99s. The five legacy API tests looked for root `var/artifacts/embeddings.pkl` and skipped despite a versioned build; separate real HTTP checks covered neural health/search/chat. No new skip or suppressed failure was introduced.
