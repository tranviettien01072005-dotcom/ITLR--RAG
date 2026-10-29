> **Ngữ cảnh đồ án — 2026-10-30:** Quyết định kiến trúc theo thời điểm. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../../README.md).

# ADR-004: Thiết kế đánh giá — qrels rule-based từ metadata, bootstrap CI, nhãn "human" chỉ là khung

## Trạng thái
Accepted (khung); hiện trạng nhãn human = mô phỏng, đổi khi có nhãn người thật

## Ngày
2026-10-27

## Bối cảnh
Cần đo retrieval (P/R/HitRate/MRR/MAP/NDCG), CF, beyond-accuracy (coverage/diversity/novelty),
robustness, latency, ablation, significance — reproducible một lệnh (`eval/run_all.py`). Tài nguyên
cận biên: KHÔNG có nhãn người thật; LLM judge không khả dụng trong môi trường build (không key).

## Quyết định
- **Retrieval qrels**: sinh `eval/make_judgments.py` rule-based TRỰC TIẾP từ metadata catalog
  (topic token khớp + chuyên mục) trên TOÀN catalog — KHÔNG chạy retrieval để sinh nhãn,
  tránh vòng tròn "hệ thống nhắc từ xuất hiện phổ biến trong catalog rồi được thưởng".
  Grade: 2 = cùng chuyên mục, 1 = chéo chuyên mục, 0 = không lưu.
- **Ý nghĩa thống kê**: bootstrap CI 95% + permutation test (`itlr/eval/significance.py`) bằng
  seed 20240623; ablation chạy cả bộ sạch và bộ NHIỄU (noisy — flexible kháng lỗi chính tả/thiếu dấu).
- **Human eval là KHUNG**: `human_judgments.csv` có cột `human_label` trống để người gán
  (workflow ẩn nhãn tự động trong `prepare_labeling_sheet.py` chống thiên lệch). Chế độ
  `--simulate-human` CHỈ để chạy qua được pipeline (nhãn ghép từ qrels với ~88% đồng thuận
  mô phỏng); mọi report phải ghi rõ "nhãn mô phỏng" khi dùng.
- **Generation**: đo TRỰC TIẾP citation `[item_id:ID]` (valid/in-context — không xấp xỉ) +
  hallucination rate; groundedness/relevancy là **proxy rule-based** (n-gram, token-overlap),
  buộc ghi rõ là xấp xỉ trong report; LLM-judge để sau khi có DeepSeek key thật.
- **Off-topic gate**: ngưỡng chốt bằng dữ liệu (`eval/eval_offtopic.py`): AUC/ROC trên
  `var/data/eval/offtopic_testset.csv` (121 câu hand-curated: 60 IT / 61 ngoài chủ đề).

## Phương án đã cân nhắc
- **qrels bằng polling LLM**: không key trong môi trường build + tốn + ko reproducible-second —
  bị loại (giữ làm tương lai khi có key).
- **Chỉ đo NDCG, bỏ CI**: dễ nhưng không khẳng định ý nghĩa — bị loại (bootstrap là chuẩn rẻ).
- **Sinh nhãn từ kết quả hệ thống đang đánh giá**: vòng tròn, đánh phồng P/R — bị loại rõ ràng.

## Hệ quả
- Mọi con số tái lập được: `python eval/run_all.py [--quick]` → `reports/*.md|csv|json`.
- Report HIỆN TẠI dùng qrels rule-based — đọc hiểu là nhãn metadata, không phải nhãn người.
- Chỉ tiêu sau: thay `human_label` bằng nhãn thật → Cohen's Kappa (evaluate_human.py) sẽ có nghĩa;
  chạy `python eval/eval_generation.py --llm` khi có `DEEPSEEK_API_KEY` để có số generation sống.
