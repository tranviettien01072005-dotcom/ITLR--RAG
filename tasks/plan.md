> **Ngữ cảnh đồ án — 2026-10-30:** Tài liệu lịch sử: giữ số đo, phạm vi và kế hoạch tại thời điểm ghi. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../README.md).

# Implementation Plan: Product-grade RAG Learning Upgrade

## Mục tiêu

Nâng ITLR RAG từ research prototype thành một hệ thống RAG có thể vận hành, đánh giá và tái lập; đồng thời dùng chính từng phase như một giáo trình thực hành về retrieval, reranking, grounding, evaluation và production engineering.

## Nguyên tắc

- Không tối ưu điểm bằng cách thay đổi qrels hoặc làm rò thông tin giữa train/test.
- Mọi cải thiện phải có baseline, confidence interval hoặc paired significance test khi phù hợp.
- Tách rõ offline evaluation, online serving và provenance của dữ liệu/nhãn.
- Mỗi phase kết thúc bằng test, benchmark và một bài học RAG ngắn.

## Lộ trình

### Phase 0 — Baseline và an toàn

- Xoay/revoke credential trong `.env.example`; thêm secret scanning.
- Sanitize Markdown/HTML, bỏ các `innerHTML` không cần thiết.
- Bảo vệ hoặc vô hiệu hóa `/admin/reload` khi không có auth.
- Thêm giới hạn độ dài request, history và metadata; trả HTTP 4xx/5xx đúng ngữ nghĩa.

**Nghiệm thu:** không còn credential-shaped value; test payload XSS không thực thi; admin endpoint bị từ chối khi thiếu quyền; request quá lớn bị reject.

**Bài học:** threat model cho RAG và vì sao output của LLM phải được coi là untrusted input.

### Phase 1 — Evaluation đáng tin cậy

- Sửa hallucination evaluator khi `valid_ratio == 0` và khi không có citation.
- Sửa formatter NaN/unknown và bổ sung test edge cases.
- Làm `run_all.py` trả exit code khác 0 nếu bất kỳ stage nào thất bại.
- Gắn provenance cho nhãn: `human`, `simulated`, `synthetic`, `imported`.
- Lưu seed, dataset hash, config hash và git/source revision (hoặc archive hash vì repo hiện không có Git).

**Nghiệm thu:** một lỗi trong bất kỳ stage nào làm CI fail; báo cáo phân biệt rõ simulated-human; chạy lại cùng seed cho kết quả tái lập.

**Bài học:** NDCG/Recall, leakage, qrels, statistical significance và evaluation validity.

### Checkpoint A

- `pytest` pass.
- Có baseline report mới, không dùng report cũ.
- Có bảng so sánh TF-IDF, BM25, E5, E5+char, reranker.

### Phase 2 — Cải thiện retrieval có kiểm soát

- Xây query set theo nhóm intent và độ nhiễu, mỗi nhóm có qrels độc lập.
- Tuning E5 normalization, top-k, char weight và fusion weight trên validation split.
- Benchmark cross-encoder theo latency/quality; thêm cache và batch nếu có lợi.
- Kiểm tra RRF/MMR theo Pareto frontier accuracy–diversity thay vì mặc định bật tất cả.
- Tách đánh giá clean/noisy/temporal thành các track rõ ràng.

**Nghiệm thu:** báo cáo có confidence interval; không có test leakage; tăng NDCG/Recall trên holdout mà không làm p95 latency vượt SLO đã đặt.

**Bài học:** dense vs lexical retrieval, hybrid fusion, reranking, MMR và trade-off latency.

### Phase 3 — Grounded generation và streaming

- Chuẩn hóa citation schema: citation phải trỏ đến một retrieved chunk hợp lệ.
- Thêm context budget, duplicate removal và answerability/refusal policy.
- Xử lý lỗi giữa stream bằng event trạng thái rõ ràng (`partial`, `error`, `done`).
- Đánh giá groundedness, citation precision/recall và refusal precision riêng biệt.

**Nghiệm thu:** citation invalid bị bắt 100%; partial stream không bị báo thành công; câu hỏi ngoài phạm vi nhận refusal có lý do.

**Bài học:** context assembly, attribution, groundedness và failure semantics.

### Phase 4 — Packaging và vận hành

- Sửa package discovery và package-data để wheel chứa toàn bộ runtime cần thiết.
- Thêm clean-environment install smoke test.
- Pin dependency bằng lock/constraints; thêm health/readiness checks.
- Metrics: retrieval latency, rerank latency, token usage, refusal rate, citation validity, error rate.
- Tách `chatbot.py` thành các module: intent, retrieval, generation, streaming, references.

**Nghiệm thu:** wheel cài được trong môi trường sạch và chạy search/chat; có dashboard/log schema; p50/p95 có SLO.

**Bài học:** RAG observability, reproducible builds và production boundaries.

## Thứ tự triển khai đề xuất

1. Phase 0 security.
2. Phase 1 evaluation correctness.
3. Phase 4 packaging tối thiểu để mọi benchmark chạy trên artifact thật.
4. Phase 2 retrieval tuning.
5. Phase 3 generation/streaming.
6. Phase 4 observability và refactor.

## Tiêu chí thành công tổng thể

- Không có secret, XSS path hoặc unauthenticated destructive admin action.
- Evaluation tái lập và phân biệt đúng dữ liệu thật/mô phỏng.
- Holdout NDCG/Recall tăng có ý nghĩa so với baseline hiện tại.
- Citation validity và refusal precision đạt ngưỡng đã công bố.
- Wheel cài sạch, API có giới hạn và metrics đủ để debug regression.
