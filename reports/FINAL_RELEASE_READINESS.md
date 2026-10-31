# FINAL RELEASE READINESS — ITLR–RAG (2026-10-31)

| Mục | Giá trị |
|---|---|
| Branch / HEAD | `main` @ `cd58edd` (audit + hardening chưa commit theo yêu cầu) |
| Phạm vi | đóng blocker AUD-01→06, business rules, benchmark cold/warm, human packet, full gate |
| Manifest | `reports/audit-file-manifest-2026-10-31.tsv` — **868 dòng** (824 tracked + 44 file mới) |
| Evidence | `reports/final-e2e-evidence/release-2026-10-31/` + `SHA256SUMS.txt` |
| Môi trường | i7-8650U 4C/8T, 14 GiB, CPU-only; Python 3.14.4; Node 22.22.1; PostgreSQL 16; Ollama 0.40.13; Docker 29.9.2 |

## 1. Xác minh lại AUD-01 → AUD-06

| ID | Kết quả xác minh | Bằng chứng |
|---|---|---|
| AUD-01 lesson chưa duyệt | PASS: route trả 404, không ghi `lesson_progress`; progress chỉ đếm `approved` | `lesson-progress.test.ts`; PG: complete lesson pending không đổi mẫu số |
| AUD-02 đồng bộ enrollment | PASS: approve/delete chạy `syncCourseEnrollments` cho mọi user | PG: approve lesson thứ 3 → progress 33%; test SQL `DISTINCT user_id` |
| AUD-03 transaction reset | PASS: claim + đổi mật khẩu + revoke trong 1 transaction; lỗi giữa chừng rollback | PG: trong tx `new-hash/tv=1`, sau `ROLLBACK` là `old-hash/tv=0`, token không bị đánh dấu dùng |
| AUD-04 thu hồi JWT | PASS: token cũ bị từ chối sau khi `token_version` tăng; login mới nhận version mới | `auth.test.ts` (+2), `session-revocation.test.ts` |
| AUD-05 spam reset email | PASS: cooldown 60s theo tài khoản; chỉ token mới nhất active | unit test; PG: 2 request → 1 token, active = 1 |
| AUD-06 race progress | PASS: một câu `INSERT … SELECT … ON CONFLICT`, kết quả suy ra từ counts | unit test (1 upsert); PG: recompute lặp lại giữ `50%` |

**Migration `users.token_version`:**

| Kịch bản | Kết quả |
|---|---|
| DB mới, apply `schema.sql` | PASS, cột tồn tại, default `0` |
| Apply lại lần 2 (idempotent) | PASS, chỉ NOTICE "already exists" |
| DB cũ (users chưa có cột) + apply schema | PASS, user cũ nhận `token_version=0` |
| Session cũ sau khi bump version | Bị từ chối ở request kế tiếp; session mới hợp lệ |

## 2. Business rules — quyết định và test

| Rule | Quyết định | Test |
|---|---|---|
| Complete lesson của khóa **chưa enrollment** | **Cho phép** (học mở); hoàn thành lesson approved sẽ tạo/cập nhật enrollment `in_progress` | `lesson-progress.test.ts` (atomic upsert) |
| Xóa lesson **đã duyệt** bởi contributor | **Chặn** — chỉ admin; nội dung đã duyệt thuộc khóa học | test mới (403, không DELETE) |
| Logout | `/logout` chỉ xóa cookie thiết bị hiện tại; `POST /account/logout-all` tăng `token_version` thu hồi mọi JWT | `session-revocation.test.ts` |
| Reset-token cleanup | Xóa token hết hạn/đã dùng >1 ngày mỗi lần `/forgot` | test mới + SQL |
| Upload | Chỉ ảnh raster/PDF kiểm magic bytes + MIME + ≤20 MB; không phải antivirus | test hiện có (PDF hỏng bị từ chối) |
| Rate limiter | 429 + `Retry-After`; `0` tắt bucket; limiter RAM một worker | `test_api_hardening.py` |

RED→GREEN của lượt này: **4 test fail** (delete approved, logout-all, cleanup, throttle count)
→ sửa → **10/10 pass**; full Web suite **160 pass**.

## 3. Benchmark RAG cold/warm (tách thành phần)

Prompt thật: 4893 ký tự / **1387 token** (5 chunk). Reranker tắt (`DISABLE_RERANKER=1`).

| Thành phần | Cold | Warm |
|---|---|---|
| Model load (Ollama container) | 6,21s | ~0 |
| Prefill 1387 token | **43,42s @ 31,9 tok/s** | 0,148s (prefix cache) |
| Decode 20 token | 0,147s @ 13,6 tok/s | 0,151s |
| Tổng request | **49,80s** | **0,33s** |
| Retrieval (E5 + FAISS + BM25 + RRF, host) | — | p50 **145 ms**, max 410 ms (query đầu warm-up) |
| Stream tới final (host, warm) | — | p50 **3,69s**, max **32,61s** (prompt chưa cache) |
| RSS | — | Python 1,73 GiB; Ollama runner 3,82 GiB |

**Kết luận SLO 45s:** cold 49,8s > 45s chỉ vì prefill + load; ngay cả prefill đơn lẻ (43,4s)
đã gần hết budget. Trên CPU này **không thể đạt SLO** cho prompt đầy đủ. Không nới SLO, không
giảm prompt/model. Cấu hình tối thiểu cần kiểm chứng lại: prefill ≥65–70 tok/s (CPU 8–12 nhân
P-core hiện đại hoặc GPU CUDA tầm RTX 3060/4060), kèm chạy lại frozen + cold/warm.

## 4. Gate thực thi

| Gate | Kết quả | Trạng thái |
|---|---|---|
| Python pytest | 494 pass / 0 skip, 73,7s | PASS |
| Python coverage | 67,63% (3946/5835) | PASS |
| Web vitest | **160 pass / 29 file** | PASS |
| Web coverage | lines **51,42%** (724/1408), statements 48,22% | PASS |
| typecheck / lint / build / compileall / pip check | PASS | PASS |
| pip-audit | **0 advisory** (chạy lại thành công) | PASS |
| npm audit / Bandit | 0 vulnerability / 0 High | PASS |
| PostgreSQL 16 (fresh, re-apply, legacy upgrade, rollback, recompute) | PASS | PASS |
| Docker Compose staging (web image mới `9af9a2f9…`) | 25/25 check trước khi tiến trình bị server restart cắt; health/TLS/PG/backup-restore/rollback/tamper/restart PASS | PASS scoped |
| Chrome E2E (TLS CA nội bộ) | **11/11 PASS**, UI ready 23ms, socket provider đóng **78ms** | PASS |
| SSE terminal events / không lưu partial | `sources→meta→text→final→done`; cancel không final | PASS |
| Backup/restore 15 bảng row-hash | PASS | PASS |
| Artifact reload/rollback/tamper | PASS | PASS |
| Load/soak | conc1 1,93s; conc2 max 3,99s; conc4 max 7,94s; soak 134 vòng/67 chat (60 OK, 7 bị 429 do limiter 30/phút) | PASS scoped |
| Frozen generation eval | **12/12 positive accepted, 7/8 negative không-claim**; p50 2,82s, max 28,0s (prompt cache warm) | PASS (warm) |
| SLO 45s cold | 49,80s | **FAIL** |
| Human faithfulness | chưa có reviewer | **NOT VERIFIED** |
| Provider-after-cancel | không chạy lại; lần trước PASS (`done/stop`) | **NOT RE-RUN** |
| Multi-host/HA, soak dài, cold concurrency >1 | — | **NOT VERIFIED** |

## 5. RAG quality

Lượt frozen này chạy sau khi prompt đã được cache trong daemon, nên latency **không đại diện cold**;
giới hạn SLO phải đọc từ benchmark cold ở §3.

| Chỉ số | Kết quả |
|---|---|
| Retrieval (118 item, 23 query, 3 lặp): Recall@5 | **1,000** |
| MRR@5 / nDCG@5 | **0,869 / 0,9035** |
| Retrieval p50 / p95 | 67,0 / 79,6 ms |
| Frozen 20 case (Qwen2.5:3b thật, lượt này) | **12/12 positive accepted, 7/8 negative không-claim**, citation valid + verbatim; p50 2,82s / max 28,0s (cache warm), không timeout |
| Human faithfulness/entailment | **null / NOT VERIFIED** |

Không thay model/threshold/prompt/ranking trong lượt này; không có benchmark độc lập chứng minh
một thay đổi thuật toán là cải thiện, nên không đổi.

## 6. Human evaluation (chuẩn bị, chưa chấm)

- Bộ câu hỏi: frozen 20 (SHA `2a3a98e2…`, giữ nguyên) + supplement 20 (hard negative, VI/EN,
  multi-hop, prompt injection; SHA `818e3b35…`).
- Rubric 0–3 và quy trình 2 reviewer độc lập + trọng tài: `HUMAN_REVIEW_PROTOCOL.md`.
- Phiếu chấm: `human_review_scoring_sheet.csv` (40 dòng, mọi cột `human_*` để trống).
- Chưa có người chấm → unsupported-claim rate, citation precision, refusal accuracy,
  faithfulness = **null**, không tuyên bố PASS.

## 7. File thay đổi trong lượt này

`web/src/routes/api.routes.ts` (rule xóa lesson approved; giữ response progress),
`web/src/routes/auth.routes.ts` (logout-all, cleanup token, cooldown đã có từ lượt trước),
`web/src/views/account.ejs` (nút đăng xuất mọi thiết bị),
`web/src/routes/lesson-progress.test.ts`, `password-reset.test.ts`,
`web/src/routes/session-revocation.test.ts` (mới),
`reports/FINAL_RELEASE_READINESS.md`, `reports/final-e2e-evidence/release-2026-10-31/*`,
`reports/release-readiness-evidence/human_review_scoring_sheet.csv`,
README/AGENTS/CONSTRAINTS/TESTING/SECURITY/VALIDATION/PROJECT_MEMORY/CHANGELOG.
Không đổi schema hiện có (chỉ cột `token_version` từ lượt trước), API cũ, model, ranking.

## 8. Rủi ro còn lại

| Ưu tiên | Rủi ro | Xử lý |
|---|---|---|
| P0 (release) | SLO 45s cold 49,8s | hardware đạt prefill ≥65–70 tok/s rồi đo lại; không nới SLO |
| P0 (release) | Human faithfulness chưa có | 2 reviewer chấm 40 case; trọng tài khi lệch ≥2 |
| P1 | Chưa kiểm provider-after-cancel trong lượt này | chạy lại probe trên staging |
| P1 | Multi-host/HA, soak dài, cold concurrency >1 chưa đo | staging chuyên dụng/load test dài |
| P2 | Logout mặc định không thu hồi token thiết bị khác | dùng `/account/logout-all`; hoặc thêm session store |
| P2 | Soak chạm limiter chat 30/phút (7/67 request 429) | tăng limiter chỉ khi có capacity; hiện là hành vi đúng |
| P3 | Upload chỉ kiểm định dạng | AV/CDR ở hạ tầng nếu cần |
| P3 | Contributor không xóa được lesson đã duyệt (kể cả khi sai) | admin xử lý qua `/admin/docs/:id` |

## 9. Verdict

**NO-GO production.** Toàn bộ lỗi correctness/security đã đóng bằng test và kiểm chứng
PostgreSQL; staging/chrome/backup/rollback/load và security scans PASS. Hai release blocker
thật vẫn mở và không thể đóng bằng code trên hardware này: **SLO 45s cold (49,8s)** và
**human faithfulness (`null`)**. Không có tuyên bố production-ready.
