# Chạy E5 và Qwen local

Hướng dẫn chạy embedding `intfloat/multilingual-e5-base` (768d) và generation
`qwen2.5:3b` qua Ollama cho môi trường CPU-only. Cache/binary nằm ngoài Git; checkout khác
phải chuẩn bị riêng. Không gọi API trả phí trong cấu hình này.

## Điều kiện

- Cache E5 ở `var/hf` (hoặc `HF_HOME` khác), artifacts đã build/probe.
- Ollama binary/daemon khả dụng (`ollama serve` trên PATH, hoặc `var/ollama/bin/ollama`).
- `OLLAMA_BASE_URL=http://127.0.0.1:11434`, `OLLAMA_MODEL=qwen2.5:3b`.
- Model thiếu ⇒ lỗi rõ ràng, không tự thay model khác.

## Khởi chạy

Nếu chưa có daemon:

```bash
OLLAMA_HOST=127.0.0.1:11434 OLLAMA_MODELS="$PWD/var/ollama/models" \
  OLLAMA_NO_CLOUD=true OLLAMA_NUM_PARALLEL=1 OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_CONTEXT_LENGTH=4096 var/ollama/bin/ollama serve
```

API (terminal khác), không nạp key cloud:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:3b OLLAMA_TIMEOUT=45 \
  DISABLE_RERANKER=1 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  ITLR_REQUIRE_ARTIFACT_MANIFEST=1 \
  .venv/bin/python -m uvicorn itlr.api.server:app \
  --host 127.0.0.1 --port 8000 --workers 1 --no-proxy-headers
```

`OLLAMA_TIMEOUT` là total generation deadline (giây, hữu hạn dương), áp dụng cho cả chat và
stream; đặt quá lớn không biến request chậm thành đạt SLO. `USE_OLLAMA=0` chỉ dùng
template/extractive — phải giữ đúng nhãn mode khi lưu kết quả.

Reranker CrossEncoder (`BAAI/bge-reranker-base`) bật mặc định khi có model; lệnh mẫu ở
đây tắt bằng `DISABLE_RERANKER=1` vì chưa đo chất lượng/latency trên CPU. Nếu model thiếu,
engine log WARNING và giữ thứ tự retrieval. Bật lại phải đo trước khi kết luận.

## Hiệu năng thực đo (i7-8650U, 8 thread, CPU-only)

| Phép đo | Giá trị |
|---|---|
| Prefill prompt 1387 token (cold) | **40–51s** (27–34,5 tok/s) |
| Flash attention (`OLLAMA_FLASH_ATTENTION=1`) | **+10,6%** prefill (34,5 tok/s) |
| KV cache `q8_0` | chậm hơn (26,9 tok/s) |
| Cache hit cùng prompt | prefill 0,14s, tổng ~0,34s |
| Decode | 6,8–15,4 tok/s (chỉ cần 10–20 token cho chọn chunk) |
| Cold start container → `/health` | 42s |

Vì vậy **SLO 45s không đạt** cho prompt uncached trên hardware này. Cần prefill ≥65–70 tok/s
(CPU P-core mới hoặc GPU) và chạy lại frozen + cold/warm. Không hạ model/context, không nới
SLO để hợp thức hóa. Benchmark và A/B: [certification §11–§12](../reports/FINAL_E2E_CERTIFICATION.md).

## Smoke có chủ đích

Script dưới tự khởi chạy/dừng API trên cổng **18001** và thực hiện inference thật; kiểm
cổng trống và model sẵn sàng trước khi chạy:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python scripts/verify_local_models.py
```

Smoke chỉ chứng minh model chạy trong cấu hình đó; không chứng minh faithfulness, hallucination
rate, corpus hiện hành hay luồng Web/DB. HTTP 200 không phải generation PASS.

## Utility và giới hạn

- `itlr.utils.repickle` chỉ dùng trên **bản sao offline tin cậy** khi mismatch sklearn; không
  chạy trên active data, không cấp lại manifest/activation.
- Không suy ra DeepSeek live hay Docker đã kiểm chứng từ inference Ollama local.
- Model-internal cancellation ACK, capacity/soak và context token boundaries **chưa VERIFIED**;
  transport cancellation đã đo ở staging (socket provider đóng ~55ms).
