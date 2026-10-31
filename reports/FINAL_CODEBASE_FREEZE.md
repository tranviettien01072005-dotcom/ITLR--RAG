# FINAL CODEBASE FREEZE — ITLR–RAG (2026-10-31)

| Mục | Giá trị |
|---|---|
| Branch / HEAD | `main` @ `cd58edd`; working tree chứa đợt audit + hardening **chưa commit** (theo yêu cầu, không commit/push) |
| Bản sửa được bảo toàn | AUD-01→06, `token_version` + migration, business rules (delete approved, logout-all, token cleanup), toàn bộ regression test |
| Code | 196 file `.py` (**23.196 dòng**), 61 `.ts` (**4.668 dòng** trong `web/src`), 58 file test Python, 25 file test TS |
| Manifest | `reports/audit-file-manifest-2026-10-31.tsv` (868 dòng: 824 tracked + file mới) |
| Evidence | `reports/final-e2e-evidence/release-2026-10-31/`, `SHA256SUMS.txt` |

## 1. Dọn dẹp code (lượt này)

| Thay đổi | Lý do | Ảnh hưởng |
|---|---|---|
| `itlr/collect/normalize.py`: bỏ import `content_hash` | không dùng (chỉ dùng `title_similarity`) | không đổi hành vi; test normalize/pipeline PASS |
| `web/src/routes/admin.routes.ts`: `req` → `_req` | tham số không dùng | không đổi hành vi |
| `web/src/routes/auth.routes.ts`: `req` → `_req` | tham số không dùng | không đổi hành vi |

Xác minh dead code:

- `tsc --noUnusedLocals --noUnusedParameters`: **0 lỗi** (trước đó 2).
- `pyflakes`: còn 39 cảnh báo, **tất cả là chủ ý**:
  - re-export tương thích có comment/noqa: `itlr/chatbot/chatbot.py` (legacy helper block),
    `itlr/core/recommender.py` (display helpers cho pickle/legacy import),
    `itlr/collect/__init__.py` (`# noqa: F401`), `itlr/eval/__init__.py` (`# noqa: F401`).
  - import có side effect: `itlr/utils/runtime_patches` (`# noqa`), `EducationalChatbot`
    trong `eval/eval_v2_real.py` (`# noqa` import-check).
  - 1 redefinition cục bộ (`row_to_dict`) trong nhánh legacy của chatbot — không sửa vì
    nằm trong compatibility path, không có lỗi hành vi.
- Không xóa file nào: không tìm thấy file chết an toàn để xóa. `itlr/core/bm25.py` được giữ
  vì pickle cũ tham chiếu (ràng buộc AGENTS).
- Không đổi dependency, model, threshold, prompt, ranking, schema hiện có, API contract.

## 2. Rà soát lỗi và bảo mật (không phát hiện lỗi mới)

| Vùng | Kết quả | Cách xác minh |
|---|---|---|
| Auth / JWT revocation | PASS | `auth.test.ts` (token_version), `session-revocation.test.ts`, PG rollback drill |
| Password reset | PASS | transaction claim+update+revoke; PG rollback giữ `old-hash/tv=0`; cooldown theo tài khoản |
| Rate limiting | PASS | 429 + `Retry-After`, bucket `0` tắt, search/chat độc lập (`test_api_hardening.py`) |
| Lesson approval / enrollment / progress | PASS | 404 lesson chưa duyệt; chỉ đếm `approved`; sync mọi user; recompute một câu SQL |
| Concurrency | PASS (theo thiết kế) | một `INSERT … SELECT … ON CONFLICT`; PG recompute lặp lại giữ nguyên kết quả |
| Input validation / SQL | PASS | Pydantic + zod; SQL tham số hóa; SQL động duy nhất ở `sync-courses` lấy header từ whitelist CSV |
| XSS / CSRF | PASS | EJS escape; markdown `html:false` + escape trước citation; CSRF cookie+header cho mọi method ghi |
| Upload | PASS | magic bytes + MIME + giới hạn; file lỗi zero buffer; không phải antivirus (ghi rõ) |
| Path traversal / SSRF | PASS (phạm vi) | tệp phục vụ theo id DB/blob; link chỉ http(s); recommender URL do operator cấu hình |
| SSE lifecycle | PASS | yêu cầu `final` + `done` + EOF sạch; event sau done bị từ chối; cancel đóng socket provider |
| Index lifecycle / artifacts | PASS | probe/activate/reload/rollback/tamper/restart đã drill ở lượt release |
| Citation / prompt injection | PASS (phạm vi) | binding verbatim + id validation; system prompt chặn instruction trong nguồn; chưa có red-team độc lập |
| Secret handling | PASS | secret scan 0 hit trên toàn bộ file thay đổi |

Không có P0/P1 mới trong phạm vi kiểm chứng. Các giới hạn đã biết (SLO, human eval, HA,
upload ≠ AV, provider-after-cancel) giữ nguyên và được ghi ở §5.

## 3. Quality gates (chạy mới sau cleanup)

| Gate | Kết quả | Trạng thái |
|---|---|---|
| Python pytest | **494 passed / 0 skip**, 73,54s | PASS |
| Python coverage | **3946/5835 = 67,63%** | PASS |
| compileall / pip check | PASS | PASS |
| Web vitest | **160 passed / 29 file** | PASS |
| Web coverage | lines **724/1408 = 51,42%**; statements 48,22%; branches 39,49% | PASS |
| typecheck / ESLint / build | PASS | PASS |
| npm audit | **0 vulnerability** | PASS |
| pip-audit | **0 advisory** | PASS |
| Bandit | **0 High** | PASS |
| Secret scan (changed files) | **0 hit** | PASS |
| `git diff --check` | PASS | PASS |
| PostgreSQL 16 (fresh/re-apply/legacy/rollback/recompute) | PASS ở lượt release; **không chạy lại** lượt này (SQL không đổi) | PASS (prior) |
| Docker Compose / Chrome 11/11 / TLS / backup / rollback | PASS ở lượt release; **không chạy lại** lượt này (cleanup không đổi hành vi) | PASS scoped (prior) |
| Frozen 20 case | 12/12 positive, 7/8 negative (warm cache) ở lượt release | PASS (warm) |
| SLO 45s cold | 49,80s | **FAIL** |
| Human faithfulness | chưa có reviewer | **NOT VERIFIED** |
| Multi-host / soak dài | — | **NOT VERIFIED** |

## 4. Trước / sau

| Chỉ số | Trước lượt này | Sau |
|---|---|---|
| Python test | 494 | **494** |
| Web test | 160 | **160** |
| Python coverage | 67,63% | **67,63%** |
| Web lines coverage | 51,42% | **51,42%** |
| tsc unused symbols | 2 | **0** |
| Import không dùng (pyflakes) | 40 | **39** (toàn bộ là re-export/noqa có chủ ý) |
| File bị xóa | — | **0** |
| Dependency thay đổi | — | **0** |
| LOC Python / `web/src` TS | 23.196 / 4.668 | **23.196 / 4.668** (3 sửa nhỏ, không tăng net) |

Không hợp nhất test nào; không giảm coverage; không đổi hành vi.

## 5. Rủi ro còn lại

| Ưu tiên | Rủi ro | Trạng thái |
|---|---|---|
| Release blocker | Cold SLO 45s = 49,80s trên CPU hiện tại | **FAIL** — cần hardware prefill ≥65–70 tok/s + đo lại cold/warm |
| Release blocker | Human faithfulness/entailment | **NOT VERIFIED** — packet/rubric/sheet 40 case sẵn sàng, chưa có reviewer |
| P1 | Provider-after-cancel, cold concurrency >1, soak dài, multi-host/HA | NOT VERIFIED |
| P2 | `/logout` không thu hồi token thiết bị khác (dùng `/account/logout-all`) | chấp nhận, có đường thay thế |
| P2 | Soak chạm limiter chat 30/phút (7/67 request 429) | hành vi đúng của limiter |
| P3 | Upload không phải antivirus; xóa lesson đã duyệt cần admin | ghi rõ trong SECURITY/DEPLOY |
| P3 | 39 cảnh báo pyflakes là re-export/noqa có chủ ý | đã phân loại ở §1 |

## 6. Verdict

- **CODE FREEZE READY** — code sạch trong phạm vi kiểm chứng: không dead code an toàn để xóa,
  tsc strict sạch, 494/160 test PASS, coverage không giảm, security/dependency scans 0, không
  lỗi P0/P1 mới, không thay đổi API/schema/model/ranking ngoài các bản sửa đã có test.
- **PRODUCTION NO-GO** — hai release blocker không thể đóng bằng code trên hardware này:
  cold SLO 45s (49,80s) và human faithfulness (`null`). Không có tuyên bố production-ready.

Evidence chi tiết: `reports/FINAL_RELEASE_READINESS.md`,
`reports/FINAL_PRODUCTION_AUDIT.md`, `reports/final-e2e-evidence/` (+ `SHA256SUMS.txt`).
