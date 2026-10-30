# ADR-004: Đánh giá có provenance và giới hạn diễn giải

## Status

Accepted. Historical decision; current runtime evidence is maintained in reports/VALIDATION.md.


Sản phẩm: **ITLR–RAG | Intelligent IT Learning Platform**. Accepted, 2026-10-27.
Khung đánh giá được chấp nhận; nhãn người thật và generation độc lập còn cần bổ sung.
Bằng chứng theo lần chạy: [Validation](../../reports/VALIDATION.md).

## Context

Cần so retrieval, CF, robustness, coverage/diversity/novelty, latency và ablation theo cách
có thể tái lập. Môi trường ban đầu không có nhãn độc lập của người dùng thật hoặc key LLM judge.

## Decision

- `eval/make_judgments.py` sinh qrels trực tiếp từ metadata toàn catalog: topic-match và
  category, grade 2 cùng category, 1 chéo category, 0 không lưu. Không dùng ranking đang
  đánh giá để tự sinh relevance labels; nhãn metadata vẫn có thiên lệch riêng.
- Bootstrap CI 95% và permutation test dùng seed 20240623. Chạy riêng clean và noisy
  để phân biệt độ chính xác với khả năng chịu lỗi chính tả/thiếu dấu.
- `human_judgments.csv` có cột `human_label` trống; phiếu gán nhãn ẩn nhãn tự động.
  `--simulate-human` chỉ kiểm pipeline bằng nhãn mô phỏng khoảng 88% đồng thuận.
  Báo cáo phải ghi rõ simulated; không gọi kết quả đó là đánh giá người thật.
- Generation kiểm citation `[item_id:ID]` thuộc nguồn đã chọn. Groundedness/relevancy theo
  n-gram hoặc token-overlap là proxy rule-based. Citation ID hợp lệ không chứng minh
  entailment, faithfulness hay tỷ lệ hallucination ngữ nghĩa; chỉ tiêu chưa đo giữ `null`.
- Off-topic dùng bộ 121 câu hand-curated (60 IT / 61 ngoài chủ đề) trong
  `var/data/eval/offtopic_testset.csv`; thay ngưỡng phải có calibration tương ứng dữ liệu/runtime.

## Alternatives

LLM-generated qrels không sẵn trong môi trường và cần đánh giá chi phí, độ ổn định, thiên lệch.
Chỉ báo NDCG mà thiếu CI không mô tả bất định. Sinh nhãn từ kết quả retrieval tạo vòng tròn
và bị loại.

## Consequences

Release diagnostics 2026-10-30 bổ sung `eval/release_queries.jsonl`: 23 truy vấn từ
snapshot thật, có quote evidence và được đóng băng trước khi chạy ranking. Nhãn vẫn
là engineer-authored, không phải independent human panel; qrels chưa exhaustive.
`precision_judged` chỉ so với các item đã gán nhãn, không coi mọi item chưa gán nhãn
là sai theo đánh giá người thật. Câu không có đáp án báo riêng empty-result rate;
không diễn giải thành generation refusal accuracy. Neural và generation chưa đo
vẫn giữ `null`. Chi tiết: [release validation](../../reports/RELEASE_VALIDATION_2026-10-30.md).

`eval/run_all.py [--quick]` tạo báo cáo có thể tái chạy trong môi trường tương thích.
Kết quả metadata/rule-based không thay thế passage qrels độc lập hoặc đánh giá của người dùng.
Cohen’s kappa trên nhãn mô phỏng chỉ phản ánh mô phỏng. Chạy `eval_generation.py --llm`
cần provider được cấu hình và quyền gọi trả phí nếu có; kết quả mới phải ghi rõ nguồn nhãn,
config, seed và phạm vi corpus. Không suy rộng số liệu legacy sang V3.
