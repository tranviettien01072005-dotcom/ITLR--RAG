# Chạy E5 và Qwen local

Hướng dẫn cho **ITLR–RAG | Intelligent IT Learning Platform** trên Linux local. Checkpoint 2026-10-29 đã tải và thử embedding `intfloat/multilingual-e5-base` (**768d**), generation `qwen2.5:3b` qua Ollama **0.40.13**. Cache/binary nằm ngoài Git; checkout khác cần chuẩn bị riêng. Không có API trả phí trong phép thử đó.

## Điều kiện và khởi chạy

Cần E5 cache ở `var/hf`, Ollama binary tại `var/ollama/bin/ollama`, model ở `var/ollama/models` và artifacts đã build/probe. Không dùng lệnh dưới để tự tải hoặc thay index đang phục vụ. Máy mới làm theo [deployment](DEPLOY.md#chuẩn-bị-dữ-liệu-và-index); khả năng inference phụ thuộc RAM/CPU thực tế.

Từ repo root, nếu Ollama chưa lắng nghe:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/var/ollama/models" \
  OLLAMA_NO_CLOUD=true OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_CONTEXT_LENGTH=4096 var/ollama/bin/ollama serve
```

Ở terminal khác, chạy API local với paid provider keys được bỏ khỏi môi trường:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:3b OLLAMA_TIMEOUT=240 \
  DISABLE_RERANKER=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  ITLR_REQUIRE_ARTIFACT_MANIFEST=1 \
  .venv/bin/python -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000 \
  --workers 1 --no-proxy-headers
```

Giao diện chính vẫn là Web cổng 3000. Đặt `USE_OLLAMA=0` khi chỉ cần template/extractive; giữ nhãn mode đúng khi lưu kết quả. CrossEncoder bị tắt trong cấu hình CPU này vì chưa có kiểm chứng reranker thật tương ứng.

## Chạy lại smoke có chủ đích

Script dưới khởi chạy/dừng API kiểm tra riêng trên cổng **18001**. Nó thực hiện inference local; kiểm cổng trống và model sẵn sàng trước khi chạy:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python scripts/verify_local_models.py
```

[Evidence model local](../reports/LOCAL_MODELS.md) ghi build/probe/activate trên **5.000 items synthetic**, version **20261029-204546**, HTTP health/search/chat 200 và Qwen trả lời API **57,01 s** với citation retrieved **2716** hợp lệ. Smoke Qwen trực tiếp **80 token** lại không có citation. Các quan sát này chứng minh model thật đã chạy trong cấu hình đó; chưa chứng minh faithfulness, tỷ lệ hallucination, corpus thật hiện tại hoặc toàn bộ luồng Web/DB.

CF chưa build trong checkpoint này, reranker tắt. Số item và version hiện hành phải đọc `/health`/pointer, không lấy từ smoke lịch sử. Không suy ra DeepSeek live hay Docker đã kiểm chứng từ inference Ollama local.
