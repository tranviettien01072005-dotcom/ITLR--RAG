# FINAL RELEASE READINESS — ITLR–RAG (2026-10-31, final hardening)

| Mục | Giá trị |
|---|---|
| Branch / HEAD | `main` @ `e976375` + thay đổi chưa commit (observability, config fix, docs) |
| Artifacts | `20261031-170147-14c44d161680`, manifest `d802fe44…`, 178 item thật |
| Evidence | `reports/final-e2e-evidence/final-release-hardening-2026-10-31/`, `dual-mode-2026-10-31/`, `observability-2026-10-31/`, `SHA256SUMS.txt` |
| Nguyên tắc | không commit/push, không `down -v`, không xóa dữ liệu người dùng, không điểm human giả |

## 1. Đóng các khoảng trống của dual-mode E2E

| Khoảng trống | Kết quả | Bằng chứng |
|---|---|---|
| Native với **PostgreSQL host** | **PASS scoped (read)** + repair catalog | Host PG18 `127.0.0.1:5432` (user `itlr_user`, DB `itlr_web`) kết nối được; trước sync `courses=0, users=1, messages=4` → chạy `sync-courses` **0→178**, users/messages giữ nguyên; Web native `/ready` 200, `/login` 200, `/courses/5129` **200**, id lạ **404**, `/dashboard` 200 (session ký cho user hiện có, read-only) |
| Native restart persistence | **PASS** | Dừng/khởi động lại Web native trên host PG: `/ready` 200, course 200, dashboard 200; DB/messages không đổi |
| Native write E2E trên host DB | **BLOCKED / NOT VERIFIED** | `rolcreatedb=f` (không tạo DB test được); không migrate/ghi chat vào DB người dùng để tránh thay đổi dữ liệu thật |
| Docker **host Ollama override** | **PASS** | Host Ollama bind `0.0.0.0:11435` (process riêng, không restart daemon người dùng) + `host.docker.internal`; API 200, Web 200, chat `llm_extractive`, citation valid |
| Docker **tải model mới** | **PASS** | Pull `qwen2.5:3b` (1.9 GB) vào volume `itlr-local_ollama_models`; `ollama list` trong container; chat với model vừa pull `llm_extractive` + citation valid |
| Docker **logout/CSRF** | **PASS** | register 302, dashboard 200, POST chat thiếu CSRF **403**, logout 302, dashboard sau logout **302** |
| Monitoring thật | **PASS (prior run cùng cây)** | 5/5 Prometheus target up, 13 panel, 10 alert, trace `sse.chat`, Loki log, ~383 MiB RAM; không re-run sau thay đổi config-only |
| Human faithfulness | **NOT VERIFIED** | 40 case (12 positive/8 negative frozen + 20 supplement), rubric 0–3, 0 reviewer; heuristic 11/12 accepted + 7/8 negative (cấu trúc, không phải entailment) |
| Windows 11/WSL2 | **NOT VERIFIED** | Không có môi trường Windows thật; chỉ hướng dẫn |

## 2. Thay đổi và root cause

- **Config artifact override:** `ITLR_ARTIFACTS_DIR` trỏ root có `CURRENT.json` từng bị dùng trực
  tiếp → API 503 VersionError. `itlr/config.py` giờ resolve version; staging phẳng vẫn dùng trực
  tiếp. Test RED→GREEN `tests/test_config_artifact_override.py`; Native và Docker đều dùng được.
- **Host DB catalog repair:** DB native `itlr_web` có catalog rỗng (0 course) dù users/messages
  thật tồn tại — đúng lớp lỗi 404. Đã sync 178 item thật (upsert, không xóa enrollment).
- Không đổi model, threshold, prompt, retrieval ranking, schema hay API.

## 3. Quality gates (cây cuối)

| Gate | Kết quả |
|---|---|
| Python pytest | **510 passed / 0 skip**, 76s |
| Python coverage | **4109/6019 = 68,27%** |
| Web vitest | **166 passed / 32 file**, lines **52,41%** |
| typecheck / lint / build / compileall / pip check | PASS |
| pip-audit / npm audit / Bandit | **0 / 0 / 0 High** |
| Secret scan / `git diff --check` | 0 hit / PASS |
| Docker compose config (base/host/monitoring) | PASS |
| Prometheus rules + Loki/Tempo/OTel/promtail config | PASS |
| Cold SLO 45s | **FAIL** — 49,80s (CPU-only) |
| Human faithfulness | **NOT VERIFIED** (`null`) |

## 4. Tài liệu

README/DEPLOY đã có: Native (Ubuntu/Windows WSL2), Docker full stack + host Ollama, model
download, crawl/build/activate, migrate/sync, monitoring (Grafana walkthrough), backup/restore,
troubleshooting. Bổ sung ngữ nghĩa `ITLR_ARTIFACTS_DIR` (root có pointer hoặc version phẳng).
Kiểm tra link nội bộ: 0 broken.

## 5. Rủi ro còn lại

1. **Cold prompt 49,80s > 45s** trên CPU — blocker production; cần GPU/CPU mạnh hơn, đo lại.
2. **Human faithfulness** chưa có reviewer độc lập → mọi kết luận chất lượng vẫn `null`.
3. Native host DB chỉ **read**; write E2E trên DB người dùng chưa làm (thiếu quyền tạo DB, tránh
   thay đổi dữ liệu thật). Write E2E đã PASS trên DB cô lập (container).
4. Windows/WSL2, HA/soak dài, TLS production: **NOT VERIFIED**.
5. Monitoring chưa soak; cAdvisor privileged/promtail docker.sock là trade-off bảo mật.
6. Host DB `itlr_web` đã được sync 178 catalog (additive). Nếu người dùng muốn rollback catalog
   cần backup/restore DB theo quy trình, không xóa row bằng tay.

## 6. Verdict

- **LOCAL READY** — Native (host PostgreSQL + app native) và Docker (container model + host Ollama
  override) chạy thật; RAG 178 item; Web/DB/SSE/persistence/logout/CSRF/restart verified.
- **DEMO READY (scoped)** — dữ liệu thật, single-host; cảnh báo cold ~50s, không SLA, không human eval.
- **PRODUCTION NO-GO** — cold SLO 45s và human faithfulness chưa đạt; HA/Windows/soak chưa kiểm.

---

## (Historical) FINAL RELEASE READINESS — ITLR–RAG (2026-10-31, first pass)


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
