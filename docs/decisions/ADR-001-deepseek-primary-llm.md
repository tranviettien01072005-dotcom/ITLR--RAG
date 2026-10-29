> **Ngữ cảnh đồ án — 2026-10-30:** Quyết định kiến trúc theo thời điểm. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../../README.md).

# ADR-001: DeepSeek là LLM chính, đi qua tầng `llm_client` thống nhất

## Trạng thái
Accepted

## Ngày
2026-10-27

## Bối cảnh
Chatbot cần LLM sinh câu trả lời grounded. Trước khi hoàn thiện, code gọi LLM nằm rải rác
trong `itlr/chatbot/chatbot.py`: nhánh OpenAI SDK trong `try_llm_response`/`try_llm_response_stream`
và hàm Ollama (`_ollama_reachable`, `_ollama_model`, `_stream_ollama`) tự quản probe/cache riêng.
Yêu cầu dự án: DeepSeek là LLM chính, chỉ đảm nhiệm GENERATION (retrieval — E5/BGE + BM25/TF-IDF +
RRF + ANN + Cross-Encoder + MMR — không đổi), retry/backoff + timeout + token tracking, không log
key, chống prompt-injection, trả lời phải có trích dẫn `[item_id:ID]`.

## Quyết định
Tạo `itlr/chatbot/llm_client.py` làm tầng LLM DUY NHẤT:
- Thứ tự provider: **DeepSeek → OpenAI → Ollama**, cấu hình bằng env
  (`DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL=https://api.deepseek.com`, `DEEPSEEK_MODEL`;
  `OPENAI_API_KEY`; `USE_OLLAMA`/`OLLAMA_*`).
- `chat()`/`stream()` với retry exponential backoff + timeout mỗi attempt; lỗi cuộn lên thành
  `LLMError` (không nuốt), adapter chatbot log WARNING rồi rơi về template — hợp đồng trả về
  `None`/generator rỗng của chatbot giữ nguyên.
- `trim_messages` (ngân sách ~16k ký tự, giữ system + lượt mới nhất), `usage_snapshot()`
  (tokens + chi phí ước theo `PRICE_PER_1M`), `mask_key` mọi điểm log.
- Chatbot chỉ delegate: `try_llm_response`, `try_llm_response_stream`, `_llm_available`
  gọi xuống `llm_client`; logic Ollama cũ trong chatbot gỡ bỏ (zg đã chuyển sang llm_client).

## Phương án đã cân nhắc
- **Giữ logic LLM rải rác trong chatbot + thêm nhánh DeepSeek**: nhanh nhưng trùng lặp
  retry/usage/che-key ở mỗi nhánh và không thể test thống nhất — bị loại.
- **Dùng framework agent nặng (LangChain…)**: thêm dependency lớn cho nhu cầu 1 cuộc gọi
  chat completions — bị loại.
- **Thay retrieval bằng embedding của DeepSeek**: trái yêu cầu (DeepSeek CHỈ generation)
  và cần build lại toàn bộ artifacts — bị loại.

## Hệ quả
- DeepSeek dùng OpenAI-compatible SDK (`base_url=https://api.deepseek.com`) — không cần SDK riêng.
  Nguồn chính thức (đã verify 2026-10-27): https://api-docs.deepseek.com/ — "base_url (OpenAI)
  `https://api.deepseek.com`", `model: deepseek-flash | deepseek-v4-pro`; `deepseek-flash`
  hiện do DeepSeek-V4.1-Flash-1017 phục vụ. Bảng giá trong `PRICE_PER_1M` là ước tính
  (chưa verify từ trang pricing chính thức).
- Đổi model chỉ bằng env `DEEPSEEK_MODEL`; mặc định `deepseek-flash` vừa khớp yêu cầu đề
  bài vừa là tên model hợp lệ theo tài liệu chính thức (lựa chọn khác: `deepseek-v4-pro`).
- Khi repo không có key: hệ thống vẫn chạy đầy đủ qua template; `--llm` của eval fail-fast
  (rc=2) để không nhầm số liệu template thành số LLM.
- Testing được mock ở tầng `_make_client` — 12 test llm_client + 7 test adapter.
