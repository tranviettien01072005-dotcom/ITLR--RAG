# FINAL PRODUCTION AUDIT — ITLR–RAG (2026-10-31)

| Mục | Giá trị |
|---|---|
| Branch | `main` (không commit/push trong lượt audit) |
| HEAD | `cd58edd` — docs/evidence commit |
| Worktree | có thay đổi chưa commit của lượt audit này (danh sách §5) |
| Môi trường | Linux, i7-8650U 4C/8T, 14 GiB, Python 3.14.4, Node 22.22.1, PostgreSQL 16 container, Ollama 0.40.13 (không gọi cloud) |
| Manifest | `reports/audit-file-manifest-2026-10-31.tsv` — **824 file Git-tracked + 18 file mới của audit = 842 dòng** |
| Evidence | `reports/final-e2e-evidence/audit-2026-10-31/` |

## 1. Phạm vi và phương pháp

Kiểm kê toàn bộ file được Git theo dõi (824) và 18 file audit mới: 196 `.py`, 61 `.ts`, 30 `.ejs`, 16 config
(`yml`/`example`/`ini`/Dockerfile/Caddyfile), 74 `.md`, cùng data/evidence/log. Manifest ghi
từng file với `kind` và mức kiểm tra:

| Status | Số file | Nghĩa |
|---|---:|---|
| `read` | 60 | đọc trực tiếp trong audit (hoặc đọc lại sau khi sửa) |
| `suite` | 225 | chạy qua pytest/vitest/typecheck/lint/build/compileall, không đọc từng dòng |
| `structure` | 95 | config/asset: kiểm tồn tại, tham chiếu, build |
| `adr` | 12 | decision record |
| `current-doc` | 4 | tài liệu hiện hành |
| `historical` | 428 | báo cáo/evidence/log đã đóng băng, **không sửa** |

Không dùng báo cáo cũ làm bằng chứng cho code hiện tại: mọi kết luận PASS dưới đây đến từ
lần chạy mới, trừ các gate ghi rõ `NOT RE-RUN`.

## 2. Phát hiện và xử lý

Không có **P0** (không tìm thấy auth bypass, RCE, lộ secret). Các lỗi P1/P2 đã sửa:

| ID | Sev | Phát hiện | Root cause | Fix |
|---|---|---|---|---|
| AUD-01 | P1 | Lesson **chưa duyệt** vẫn `POST /lessons/:id/complete` được và bị tính vào progress | query chỉ lấy `course_id`; `done` đếm mọi `lesson_progress` bất kể `approved` | từ chối lesson `approved=false`; đếm `done` chỉ khi `l.approved` |
| AUD-02 | P1 | Approve/delete lesson làm progress của **người học khác** sai (mẫu số đổi, chỉ người thao tác được tính lại) | recompute chỉ chạy cho `req.user` | `syncCourseEnrollments(courseId)` một câu SQL cho mọi user bị ảnh hưởng |
| AUD-03 | P1 | Reset password không transaction: token bị đánh dấu dùng rồi mới đổi mật khẩu → lỗi giữa chừng làm user mất token mà mật khẩu cũ vẫn hiệu lực | 3 câu lệnh rời, không rollback | `withTransaction`: claim token + đổi mật khẩu + vô hiệu token khác + tăng `token_version` |
| AUD-04 | P1 | JWT cũ vẫn dùng được sau khi đổi/reset mật khẩu (7 ngày) | token không có trạng thái thu hồi | thêm `users.token_version` (ALTER idempotent), JWT claim `tv`, `loadUser` so khớp; đổi/reset tăng version |
| AUD-05 | P2 | Spam email reset theo tài khoản (limiter chỉ theo IP) | mỗi request tạo token + gửi mail | cooldown theo tài khoản `RESET_EMAIL_COOLDOWN_SECONDS` (60s) + chỉ giữ token mới nhất |
| AUD-06 | P2 | Race khi tính progress: 2 SELECT rồi upsert, hai request đồng thời ghi đè kết quả cũ | read-modify-write không nguyên tử | progress tính bằng **một** `INSERT … SELECT … ON CONFLICT` |

### Thay đổi theo file

| File | Thay đổi |
|---|---|
| `web/src/services/lesson-progress.ts` *(mới)* | `recomputeLessonProgress` (1 câu SQL, chỉ approved) và `syncCourseEnrollments` (mọi user) |
| `web/src/routes/api.routes.ts` | lấy `approved`; từ chối lesson chưa duyệt; dùng service mới; delete → sync course; giữ response `{ok, status, progress}` |
| `web/src/routes/admin.routes.ts` | approve/delete dùng `RETURNING course_id` và sync enrollment |
| `web/src/routes/auth.routes.ts` | login/register mang `token_version`; reset dùng transaction; cooldown email; đổi mật khẩu tăng version + re-sign session hiện tại |
| `web/src/middleware/auth.ts` | `signToken` phát `tv`; `loadUser` so `tv` với DB, token cũ mất hiệu lực |
| `web/src/db/pool.ts` | `withTransaction` (BEGIN/COMMIT/ROLLBACK, release luôn) |
| `web/src/db/schema.sql` | `ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0` |
| `web/src/middleware/auth.test.ts` | +2 test thu hồi token |
| `web/src/routes/lesson-progress.test.ts` *(mới)* | 4 test |
| `web/src/routes/password-reset.test.ts` *(mới)* | 3 test |
| `web/src/db/pool.test.ts` *(mới)* | 2 test transaction |
| `reports/FINAL_PRODUCTION_AUDIT.md`, `reports/audit-file-manifest-2026-10-31.tsv` | báo cáo + manifest |
| README/AGENTS/CONSTRAINTS/TESTING/SECURITY/DEPLOY/VALIDATION/PROJECT_MEMORY/CHANGELOG | số liệu và hành vi mới |

Không đổi: API path/contract khác, database schema cũ (chỉ thêm cột), artifacts, model,
threshold, prompt, ranking. Không thêm/nâng dependency.

## 3. Bằng chứng RED → GREEN

RED trước khi sửa (4 file test mới/cập nhật):

```
 Test Files  4 failed (4)
      Tests  9 failed | 8 passed (17)
```

GREEN sau khi sửa:

```
 Test Files  4 passed (4)
      Tests  17 passed (17)
```

Toàn bộ Web suite: **157 passed / 29 file** (trước audit 146/26). Python suite: **494 passed /
0 skip** (không đổi, code Python không sửa).

Kiểm chứng SQL trên PostgreSQL 16 thật (container dùng một lần, `evidence/schema-logic-check.sql`):

| Bước | Kết quả |
|---|---|
| Apply `schema.sql` (gồm ALTER mới) | PASS; `users.token_version` tồn tại |
| User hoàn thành 1/3 lesson approved | `in_progress 33` |
| Approve thêm 1 lesson (mẫu số đổi) | `in_progress 33` → (sync toàn course) |
| Hoàn thành đủ lesson approved | `completed 100` |
| Complete lesson **chưa duyệt** | Không tăng mẫu số/tử số |
| `UPDATE users … token_version + 1` | PASS (version 0 → 1) |
| Cooldown reset: request thứ 2 trong 60s | 0 token mới; còn đúng 1 token active |

## 4. Quality gates

| Gate | Kết quả | Trạng thái |
|---|---|---|
| Python pytest | **494 passed / 0 skip**, 73,72s | PASS |
| Python coverage statements | **3946/5835 = 67,63%** | PASS (không giảm) |
| compileall / pip check | PASS | PASS |
| Web vitest | **157 passed / 29 file** | PASS |
| Web coverage | lines **710/1401 = 50,67%**; statements 47,58%; branches 38,7%; functions 41,39% | PASS (tăng từ 47,05%) |
| typecheck / ESLint / build | PASS | PASS |
| npm audit / minimatch | **0 vulnerability**; minimatch 11.0.3 | PASS |
| Bandit | **0 High** (Medium/Low đã triage) | PASS |
| pip-audit | PyPI read timeout | **BLOCKED** lượt này (lần chạy trước: 0 advisory) |
| PostgreSQL 16 schema + logic | PASS trên container dùng một lần | PASS |
| Docker Compose staging / Chrome 11/11 / TLS / backup-restore | không chạy lại trong audit này | **NOT RE-RUN** (evidence §11–§12 giữ nguyên) |
| Frozen generation eval | không chạy lại (không đổi RAG) | **NOT RE-RUN** — lần gần nhất 11/12 positive, 7/8 negative |
| SLO 45s (Qwen CPU, prompt uncached) | prefill 40–51s | **FAIL** (không nới) |
| Human faithfulness/entailment | chưa có reviewer | **NOT VERIFIED** (`null`) |
| Capacity/soak dài/multi-host | — | **NOT VERIFIED** |

## 5. RAG: trước/sau

Không thay đổi model, threshold, prompt hay thuật toán (điều kiện của yêu cầu: chỉ đổi khi có
benchmark độc lập chứng minh). Đo lại retrieval trên corpus thật (118 item, 23 query,
3 lần lặp, `eval/eval_release_retrieval.py`):

| Chỉ số | Lần này | Ghi chú |
|---|---|---|
| Recall@5 | **1,000** | lexical diagnostics, qrels engineer-authored |
| MRR@5 | **0,869** | khác bộ query/qrels so với số lịch sử 0,9375 — không so trực tiếp |
| nDCG@5 | **0,9035** | như trên |
| p50 / p95 / p99 | **66,96 / 79,57 / 82,62 ms** | retrieval lexical, không gồm LLM |
| Throughput tuần tự | **15,18 qps** | một process |
| Peak RSS | **334,4 MiB** | high-water cả tiến trình đo |
| Neural V3 / CrossEncoder / faithfulness / citation support | `null` | chưa đo |

SLO 45s của generation vẫn **FAIL** trên CPU này (prefill prompt 1387 token 40–51s); thay đổi
web không ảnh hưởng. Không có thay đổi RAG nào được thực hiện trong audit để tránh hồi quy
chất lượng khi chưa có benchmark độc lập.

## 6. Rủi ro còn lại

| Ưu tiên | Rủi ro | Hướng xử lý |
|---|---|---|
| P1 | SLO 45s không đạt trên CPU hiện tại | hardware/GPU đạt prefill ≥65–70 tok/s; chạy lại frozen + cold/warm |
| P1 | Human faithfulness/entailment chưa có | 2 reviewer độc lập + trọng tài theo `HUMAN_REVIEW_PROTOCOL.md` |
| P1 | pip-audit lượt này BLOCKED (mạng) | chạy lại khi có mạng; không coi là 0 advisory mới |
| P2 | Logout chỉ xóa cookie; JWT bị thu hồi khi đổi/reset mật khẩu, không có "logout mọi thiết bị" | thêm endpoint tăng `token_version` nếu cần |
| P2 | Bảng `password_resets` không có job dọn token hết hạn | job định kỳ (không ảnh hưởng bảo mật) |
| P2 | User có thể complete lesson approved của khóa bất kỳ (tạo enrollment ngầm) | quyết định sản phẩm: yêu cầu enrollment hoặc giữ mở |
| P3 | Contributor có thể xóa lesson đã duyệt của mình (ảnh hưởng người học khác) | giới hạn xóa khi `approved` hoặc cần admin |
| P3 | Upload chỉ kiểm định dạng, không phải antivirus | CDR/AV ở tầng hạ tầng nếu cần |
| P3 | Docker/Chrome/backup không chạy lại trong audit | chạy lại staging trước release |

## 7. Verdict

**NO-GO production.** Các lỗi P1/P2 về tiến độ lesson, đồng bộ enrollment, transaction reset,
thu hồi JWT, spam email và race tính progress đã được sửa có test RED→GREEN và kiểm chứng trên
PostgreSQL 16; suite/coverage/security sạch. Hai blocker cũ vẫn nguyên: **SLO 45s** trên CPU
và **human faithfulness `null`**; ngoài ra pip-audit lượt này bị chặn bởi mạng và các gate
staging không chạy lại.
