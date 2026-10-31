# ADR-013: Giữ prompt evidence đầy đủ, không promote char budget 800/500

## Status

Accepted — đã revert promotion trong working tree, default là `None`.
Production vẫn NO-GO vì SLO 45s chưa đạt trên CPU hiện tại.
Evidence: [certification §11–§12](../../reports/FINAL_E2E_CERTIFICATION.md).

## Date

2026-10-31

## Context

Chế độ `llm_extractive` gửi cho model toàn bộ excerpt của các chunk ứng viên (5 chunk,
~4893 ký tự, 1387 token) để model chọn chunk ID. Trên CPU-only i7-8650U, prefill của
prompt này mất 40–51s, nên budget 45s bị vượt ở các case uncached; cache hit chỉ 0,14s.

Một tùy chọn có sẵn `ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET` cắt prompt view mỗi chunk
(không cắt quote hiển thị, vì binding dùng excerpt đã lưu). Trước phiên này option ở
dạng env-controlled với default `None`; có một thay đổi chưa commit đặt default 800
nhưng chưa có A/B hợp lệ (file code sửa sau khi run kết thúc, runner không set env).

## Decision

- Giữ **default `None`**: prompt đầy đủ, không cắt excerpt.
- Giữ env override cho operator đã đo trên hardware của họ; invalid/0 quay về `None`.
- **Không promote** 800 hay 500 vì A/B frozen cho thấy mất case accepted:

| Arm | Positive accepted | Case hồi quy | Prompt p50 |
|---|---|---|---|
| `None` | 11/12 | — | 4926 chars |
| `800` | 11/12 | `positive-12` → `no_selected_evidence` | 4578 (−7,1%) |
| `500` | 10/12 | `positive-07`, `positive-11` → `no_selected_evidence` | 3086 (−37,3%) |

- Kết luận SLO 45s là **hardware-bound**, không phải tham số cấu hình: cần prefill
  ≥65–70 tok/s và phải chạy lại frozen + cold/warm trước khi tuyên bố đạt.

## Alternatives

- **Budget 800**: giữ nguyên 11/12 nhưng đổi case accepted; A/B không cho thấy cải thiện
  chất lượng và vẫn vi phạm SLO ở một positive. Bị loại vì suy giảm theo case.
- **Budget 500**: giảm prompt 37% và p50 xuống 24s nhưng mất hai positive; bị loại.
- **Giảm số chunk (top-3)**: chưa thử vì ngưỡng/ranking là contract đã hiệu chỉnh; cần
  A/B riêng và có cùng rủi ro mất bằng chứng.
- **Flash attention**: miễn phí, +10,6% prefill (34,5 tok/s), nhưng vẫn không đủ để đạt
  45s với prompt đầy đủ. Nên bật ở deployment khi có hardware phù hợp; không thay thế
  A/B chất lượng.
- **Tăng timeout / giảm model / hạ context**: bị cấm vì thay đổi SLO hoặc chất lượng.

## Consequences

- Prompt vẫn lớn: mỗi request uncached tốn ~40s prefill trên CPU này; throughput cold
  xấp xỉ 1 request/40s/worker.
- Không có thay đổi runtime nào được commit; test hiện có (28 test evidence binding)
  là lưới an toàn cho helper budget.
- Khi phần cứng mới đạt prefill mục tiêu, chạy lại A/B và có thể mở ADR mới để chọn
  budget nếu nó cải thiện latency mà không mất case.
- Việc loại bỏ compression không được dùng để tuyên bố production-ready: human
  faithfulness vẫn `null`, và các gate capacity/HA vẫn chưa kiểm.
