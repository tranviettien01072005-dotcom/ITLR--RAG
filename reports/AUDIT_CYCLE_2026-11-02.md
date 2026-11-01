# Báo cáo vòng kiểm toán kỹ thuật 2026-11-02

Vòng audit trên working tree sạch tại HEAD `7feeb2d` (main), không có thay đổi sẵn trước phiên.

## 1. Phạm vi và cách tiếp cận

- Kế thừa 6+ chu kỳ kiểm toán trước (xem `docs/PROJECT_MEMORY.md`, các báo cáo lịch sử dưới
  `reports/`). Vòng này ưu tiên: xác minh checkpoint bằng chạy thật mới, soi lại các điểm
  được yêu cầu `ChunkIndex.search` pre-fusion gating, và chỉ sửa những gì chứng minh được.
- Kỹ năng áp dụng: `ponytail` (scope tối thiểu, hành động đầy đủ), `code-review-and-quality`
  (audit đa chiều), nguyên tắc `verification-before-completion` (bằng chứng trước tuyên bố).

## 2. Kết quả baseline chạy thật (chưa sửa gì)

| Gate | Kết quả | Bằng chứng |
|---|---|---|
| Python pytest | **510 PASS / 0 skip** trong 107,5s | lần chạy mới, env không key, `DISABLE_RERANKER=1` |
| Web typecheck + lint + vitest | **166 PASS (32 file)**, lines 52,41% | `npm run typecheck; npm run lint; npm test` |
| pip check | Clean | lần chạy mới |
| Bandit | **High 0** (Low 38 / Medium 26 — pickle trust boundary, urllib scheme-validated, đã nêu trong SECURITY/ADR) | lần chạy mới |
| npm audit | 0 vulnerabilities | lần chạy mới |
| pyflakes | 0 lỗi thật; 38 unused import là re-export cố chủ ý (comment "Preserve existing helper imports") | lần chạy mới |

Checkpoint trong AGENTS (510/166, High 0) **xác nhận đúng** trên code hiện hành.

## 3. Phân tích trọng điểm: `ChunkIndex.search` gate sparse bằng dense TRƯỚC fusion

**Câu hỏi:** tập ứng viên BM25 có bị giới hạn bởi dense similarity threshold trước fusion?

**Trả lời: CÓ, và điều này có chủ đích.** Tại `itlr/core/chunks.py:51-53`, tập `allowed`
lọc mọi candidate theo `dense_score >= min_relevance` trước khi tạo cả ranking dense lẫn
sparse. Hệ quả: khi `min_relevance > 0` (search mặc định `min_pct=84`), mọi kết quả trả về
luôn thỏa dense floor — chunk khớp BM25 tốt nhưng dense thấp không được trả về.

- **Tác động:** chỉ ảnh hưởng qua thay đổi thứ hạng RRF giữa các candidate đã vượt ngưỡng;
  hợp đồng "kết quả cuối phải trên floor" vẫn được giữ nguyên bởi chính cơ chế này.
- **Lựa chọn kỹ thuật:** KHÔNG thay đổi hành vi. Ngưỡng 84 là mặc định được đánh giá và ghi
  trong ADR/PROJECT_MEMORY ("Search default 84, chọn trên dev"); thay đổi candidate generation
  mà không có eval Recall@5 trên frozen benchmark thuộc nhóm bị cấm. Xác minh bằng script:
  gated trả `[item 2]` (dense 1.0), ungated trả `[item 1 (dense 0.0), item 2]` với item 1 đứng
  đầu nhờ sparse top-1.
- **Bảo vệ chống "sửa mù":** thêm test characterization
  `test_min_relevance_gates_sparse_candidates_before_fusion`
  (`tests/test_chunks_v3.py`) ghim hợp đồng hiện hành kèm điều kiện thay đổi có chủ ý
  (đổi test + eval frozen benchmark + ADR).
- **Backlog (chưa đủ bằng chứng để triển khai):** tách candidate generation dense/sparse
  độc lập rồi fusion RRF, floor áp trên kết quả cuối. Acceptance criteria: Recall@5 không
  giảm trên frozen benchmark, negatives khôngredentials trở thành claim, ADR mới.

## 4. Các phát hiện còn lại

- **Không có P0/P1 mới xác nhận được.** Các file trọng điểm flagged (chatbot, llm_client,
  api/server, engine, recommender, web routes/services/db) đã được các chu kỳ trước harden:
  retry/budget/mask key trong `llm_client`, admin token 403 khi chưa cấu hình, rate limit
  bucket, async SSE cancellation — đều đúng như checkpoint.
- Bandit Medium 26 (pickle) là trust boundary đã xử lý qua manifest SHA + builder tin cậy
  (ADR-010); B310 urllib với `base_url` validate http/https. Không có lỗ hổng mới do thay đổi
  (không thay đổi runtime runtime code nào trong phiên này).
- **Hypothesis được ghi làm backlog:** xem mục 3.

## 5. Thay đổi thực hiện

| File | Thay đổi | Lý do |
|---|---|---|
| `tests/test_chunks_v3.py` | +23 dòng, 1 test characterization | ghim hợp đồng pre-fusion gating |
| `CHANGELOG.md` | +13 dòng | ghi trạng thái vòng audit theo AGENTS |

Không thực hiện: commit/push (không được yêu cầu), migration, activation artifact, gọi API
trả phí, thay đổi runtime code.

## 6. Full regression sau thay đổi

- Python pytest: **511 PASS** (510 + 1 mới) trong 97s.
- `compileall` itlr/scripts/eval: OK.
- Kết quả các gate khác không đổi vì không có thay đổi runtime.

## 7. Trạng thái sản phẩm (không đổi so với checkpoint)

- **LOCAL READY: ĐẠT** trong phạm vi đã kiểm; **DEMO READY: ĐẠT** (native + Docker staging đã
  được chứng minh ở chu kỳ trước); **PRODUCTION: NO-GO** — human faithfulness NOT VERIFIED,
  SLO cold generation 45s FAIL hardware-bound (prefill CPU), Qwen CPU không đạt SLO cho prompt
  uncached. Không có bằng chứng mới thay đổi verdict.

## 8. Khuyến nghị tiếp theo (ưu tiên)

1. **Human faithfulness panel** (P0 cho production): chấm 40 case packet đã sẵn sàng.
2. Hardware/generation: prefill cần ≥65–70 tok/s để đạt SLO 45s — cân nhắc GPU hoặc mô hình
   nhỏ hơn có đánh giá chất lượng độc lập trước.
3. Backlog retrieval từ mục 3 — chỉ triển khai sau khi có frozen benchmark + ADR.
4. Giữ nguyên các gate hiện hành; các phép đo mới chỉ được công bố kèm phương pháp + dataset +
   hardware.
