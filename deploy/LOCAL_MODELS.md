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

`OLLAMA_BASE_URL=http://127.0.0.1:11434` chọn endpoint local tường minh. Nếu Ollama
đã chạy qua `ollama` trên PATH, dùng daemon đó; không cần khởi chạy thêm binary
trong `var/ollama`. `OLLAMA_MODEL` được giữ nguyên: thiếu model sẽ báo lỗi thay vì
tự thay bằng model khác. `OLLAMA_TIMEOUT` phải là số hữu hạn dương, áp dụng cho cả
chat và stream. API SSE hiện dùng async HTTP với total generation deadline kể cả
khi provider ngừng gửi bytes; Browser disconnect đóng upstream socket qua các tầng.
Sync public `llm_client.stream()` vẫn kiểm elapsed budget tại từng NDJSON event,
không có hard deadline trong blocking read. Provider probe/retrieval nằm ngoài
async generation budget, nên đây chưa phải end-to-end request deadline.
Khi chưa đặt, giữ timeout legacy 90/240 giây qua
`DEEPSEEK_TIMEOUT_S`/`DEEPSEEK_STREAM_TIMEOUT_S`. Các tên legacy này không chọn cloud
provider. Cả chat và stream qua adapter chung áp dụng history character budget;
đây là xấp xỉ, không phải token accounting chính xác.

Non-stream Ollama chỉ nhận response `done=true` với finish reason `stop` hoặc thiếu
reason (compatibility). Completion `length`, error hoặc schema không hợp lệ báo
`LLMError`. Khi thử máy mới, luôn unset cloud keys như lệnh trên. Không có artifacts
trong checkout thì cần build/probe staging riêng trước khi chạy health/search/chat;
không lấy kết quả smoke lịch sử dưới đây làm readiness hiện tại.

## Chạy lại smoke có chủ đích

Script dưới khởi chạy/dừng API kiểm tra riêng trên cổng **18001**. Nó thực hiện inference local; kiểm cổng trống và model sẵn sàng trước khi chạy:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 .venv/bin/python scripts/verify_local_models.py
```

[Evidence model local](../reports/LOCAL_MODELS.md) ghi build/probe/activate trên **5.000 items synthetic**, version **20261029-204546**, HTTP health/search/chat 200 và Qwen trả lời API **57,01 s** với citation retrieved **2716** hợp lệ. Smoke Qwen trực tiếp **80 token** lại không có citation. Các quan sát này chứng minh model thật đã chạy trong cấu hình đó; chưa chứng minh faithfulness, tỷ lệ hallucination, corpus thật hiện tại hoặc toàn bộ luồng Web/DB.

CF chưa build trong checkpoint này, reranker tắt. Số item và version hiện hành phải đọc `/health`/pointer, không lấy từ smoke lịch sử. Không suy ra DeepSeek live hay Docker đã kiểm chứng từ inference Ollama local.

Audit Linux 2026-10-30 mới hơn dùng 118 snapshot thật/1576 chunks trong staging
riêng: E5 build/probe PASS, nhưng API Qwen non-stream 61,15 s thiếu citation, stream
533,73 s bị cắt và final trả `insufficient_evidence`. Ở checkpoint đó chưa có elapsed
budget tại event boundaries. Không lấy HTTP 200 làm generation PASS.
Xem [full-system audit](../reports/FULL_SYSTEM_AUDIT_2026-10-30.md); không tự dùng
staging audit làm active index hoặc chạy migration/seed để thử giao diện.

Engineering continuation: test budget 2 s với Qwen thật kết thúc bằng LLMError sau
2,14 s; API HTTP404 chat/stream khoảng 6 s với citation hợp lệ. Đây là một smoke,
không phải SLO hoặc đánh giá faithfulness. Prompt ngắn/temperature khác đã thử nhưng
không đủ chất lượng để đổi runtime defaults. Search default mới 84; explicit 90
giữ floor cũ. Xem [engineering review](../reports/FINAL_ENGINEERING_REVIEW.md).

Utility `itlr.utils.repickle` chỉ dùng trên bản sao offline tin cậy; mismatch sklearn
phải rebuild bằng môi trường phù hợp. Utility ghi atomic từng file và trả lỗi khi
thất bại, không cấp lại manifest/probe hoặc activation. Không chạy trên active data.

Blocker remediation: warm/cache-hit có thể nhanh, nhưng uncached full prompt vẫn
chạm45s trên CPU này. Không giảm context/output hoặc tăng timeout để hợp thức hóa
completion. Real Stop/socket/next-request đã đo; model-internal ACK, capacity và
context token boundaries chưa VERIFIED. Phiên E2E mới: chế độ `llm_extractive`
(evidence-bound quote) xác nhận 11/12 positive frozen accepted; uncached 60s vẫn timeout.
[Evidence mới](../reports/PRODUCTION_BLOCKERS_RESOLUTION.md).
