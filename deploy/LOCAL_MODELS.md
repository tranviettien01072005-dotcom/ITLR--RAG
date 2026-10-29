> Hướng dẫn đồ án / snapshot theo thời điểm. Giao diện chính là `web/` ở cổng 3000; xem [README](../README.md). Giữ nguyên thông báo bản quyền và provenance nguồn.

# Local E5 + Qwen (installed 2026-10-29)

Models downloaded and tested: `intfloat/multilingual-e5-base` (768d), `qwen2.5:3b`.
No paid/cloud API was used. Runtime/cache are gitignored and local to this checkout.

From repository root, start Ollama if it is not already listening:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/var/ollama/models" \
  OLLAMA_NO_CLOUD=true OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_CONTEXT_LENGTH=4096 var/ollama/bin/ollama serve
```

In another terminal start Python API:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:3b OLLAMA_TIMEOUT=240 \
  DISABLE_RERANKER=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  ITLR_REQUIRE_ARTIFACT_MANIFEST=1 \
  .venv/bin/python -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000 \
  --workers 1 --no-proxy-headers
```

Repeat the real local smoke (starts/stops its own test API on port 18001):

```bash
HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python scripts/verify_local_models.py
```

See `reports/LOCAL_MODELS.md` for observed results and limits. CF is optional/unbuilt;
reranker is disabled in these tests. Model and neural index are real; catalog is synthetic.
