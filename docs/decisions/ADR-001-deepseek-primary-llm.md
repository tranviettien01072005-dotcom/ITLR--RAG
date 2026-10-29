# ADR-001: Tập trung generation trong một LLM client

Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-27.
Bản ghi quyết định tại thời điểm triển khai; cấu hình hiện hành xem [README](../../README.md)
và bằng chứng chạy xem [Validation](../../reports/VALIDATION.md).

## Bối cảnh

Chatbot cần sinh câu trả lời dựa trên nguồn, có timeout, retry, theo dõi usage và bảo vệ secret.
Logic OpenAI và probe/cache/stream Ollama từng phân tán trong `chatbot.py`, khiến các nhánh
khó kiểm thử và dễ xử lý lỗi khác nhau. LLM chỉ phụ trách generation; retrieval vẫn dùng
embeddings, lexical search, RRF và reranker của nền tảng.

## Quyết định

`itlr/chatbot/llm_client.py` là tầng generation duy nhất, chọn provider theo cấu hình:
DeepSeek → OpenAI → Ollama. DeepSeek dùng OpenAI-compatible SDK với `DEEPSEEK_API_KEY`,
`DEEPSEEK_BASE_URL=https://api.deepseek.com` và `DEEPSEEK_MODEL`; các provider còn lại dùng
`OPENAI_API_KEY`, `USE_OLLAMA` và `OLLAMA_*`.

`chat()` và `stream()` có exponential backoff, timeout từng attempt và `LLMError` rõ ràng.
Adapter chatbot chỉ delegate, ghi WARNING khi provider lỗi và giữ hợp đồng `None`/generator
rỗng cho nhánh template. `trim_messages` giữ system message và lượt mới nhất trong ngân sách
khoảng 16k ký tự. `usage_snapshot()` theo dõi token và chi phí ước tính; log phải che key.

## Phương án đã cân nhắc

- Thêm DeepSeek trực tiếp vào các nhánh chatbot: lặp retry, usage và che secret.
- Thêm framework agent: tăng dependency cho nhu cầu chat completions đơn giản.
- Dùng DeepSeek thay embeddings: mở rộng phạm vi generation và đòi rebuild artifacts.

## Hệ quả và giới hạn

Model thay bằng environment, không cần SDK riêng. Tại checkpoint 2026-10-27, ghi chép tra cứu
[DeepSeek API](https://api-docs.deepseek.com/) nêu `deepseek-flash` và `deepseek-v4-pro`, với
`deepseek-flash` được phục vụ bởi DeepSeek-V4.1-Flash-1017. Đây là thông tin lịch sử,
không xác nhận model/pricing hiện tại. `PRICE_PER_1M` là ước tính chưa đối chiếu bảng giá.

Thiếu key không ngăn template hoạt động, nhưng không chứng minh chất lượng generation.
Evaluation `--llm` phải fail-fast với rc=2 thay vì ghi kết quả template thành kết quả LLM.
Checkpoint ghi 12 test client và 7 test adapter với `_make_client` được mock; không phải
bằng chứng gọi provider thật. Không gọi API trả phí nếu chưa được phép.
