# FINAL E2E CERTIFICATION — ITLR–RAG, 2026-10-31

**Verdict: NO-GO cho production.** Mọi blocker có thể xử lý hợp lệ trong môi trường
này đã được xử lý hoặc tái xác nhận bằng hệ thật; phần còn lại là hardware-bound /
permission-bound / human-evaluation gates — không được phép tăng timeout, hạ floor
hoặc tự cấp quyền hệ thống để "hợp thức hóa" chúng.

## 1. Phạm vi và môi trường thực tế

- Host: Linux i7-8650U (4 cores / 8 threads), RAM 14 GiB, filesystem local,
  kernel 7.0.0-42. Python 3.14.4 (`.venv`), Node v22.22.1.
- Models thật: `intfloat/multilingual-e5-base` 768d (offline cache `var/hf`) và
  `qwen2.5:3b` Q4_K_M digest `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`
  qua Ollama 0.40.13 daemon thật 127.0.0.1:11434 (dùng chung, không restart).
  Không cloud API; `DEEPSEEK_API_KEY`/`OPENAI_API_KEY` unset mọi lúc.
- Corpus: 118 snapshot thật (`data/curated_resources.jsonl`) / 1576 chunks; staging
  artifacts copy riêng sang `/tmp/opencode/itlr-e2e/artifacts`. Không activation
  lên active index, không migration database production, không commit/push.
- API E2E chạy trên cổng riêng là 18560→18600, không đụng service người dùng
  (TTS service cổng 8000 của máy này giữ nguyên).
- Kế thừa: [blocker remediation 2026-10-30/31](PRODUCTION_BLOCKERS_RESOLUTION.md)
  (async transport/cancellation đã PASS phiên trước, bài này không lặp phần đã
  có bằng chứng TCP/ASGI RED→GREEN tương đương).

## 2. Khởi điểm: working tree in-flight và RED → GREEN

Làm việc trên working tree chứa work-in-flight chưa chạy chứng minh: chế độ
`llm_extractive` (evidence-bound generation) và fingerprint `/health`. Fresh
baseline tái hiện **1 FAIL** (RED):

```
FAILED tests/test_admin_security_cf.py::test_health_reports_cf_false
AssertionError: assert {..., 'items': 0, 'artifacts': None} == {'status', 'engine', 'cf', 'items'}
```

Sửa tối thiểu (không bỏ assertion, không hạ standard): test legacy đọc theo field
thay vì ghim đúng khóa. **GREEN: 489 passed (49.05s)**; chạy lại với coverage:
**489 passed (51.91s)**. Không FAIL/skip còn lại. Count tăng so baseline 457 vì
các test files in-flight (`test_evidence_binding*`, `test_loaded_fingerprint`,
`test_llm_async`, `test_stream_cancellation`) giờ được collect trong suite
toàn phần.

Fix nhỏ thứ hai trong phiên: `web/package-lock` không đọc được bằng `npm audit`
("Invalid package tree"); reconcile bằng `npm install --package-lock-only`
(không đụng `package.json`, git không đổi file lock nào).

## 3. Full regression + coverage + security (fresh, máy này)

| Gate | Kết quả fresh | Trước (baseline 457/145) |
|---|---|---|
| Python pytest | **489 PASS / 0 fail / 0 skip**, ~50s | 457/0 |
| Python statements coverage | **3922/5822 = 67,37%** | 67,24% |
| Web Vitest | **146 PASS / 26 files** | 145 |
| Web lines coverage | **648/1377 = 47,05%** (statements 44,24%) | 46,55% |
| Typecheck / ESLint / `npm run build` | **PASS, 0 warning** | PASS |
| compileall (`itlr scripts eval`) | PASS | PASS |
| pip check | PASS | PASS |
| Bandit (fresh install bandit 1.9.4) | **0 High / 26 Medium / 38 Low** | 0 High/27M/46L |
| pip-audit (fresh install) | **124 distributions, 0 advisory, 0 skipped** | clean |
| npm audit | **14 moderate — toàn bộ dev-toolchain** (eslint→minimatch<11, ejs→jake chuỗi; không advisory runtime) | 0 với lock cũ |

npm fix duy nhất là `npm audit fix --force` → hạ eslint về 4.0.0 (breaking):
**rejected**; ghi nhận như accepted-risk dev-only, same triage approach với
Bandit Medium (pickle + operator-configured URL, xem
[BANDIT_TRIAGE_2026-10-30](BANDIT_TRIAGE_2026-10-30.md)).

## 4. RAG end-to-end thật (không mock)

Crawl → ingestion: kế thừa bằng chứng build artifact (EMBEDDINGS_MANIFEST ghi E5,
118 items, 1576 chunks, faiss; catalog SHA protected trong manifest), phần runtime
sau build được chạy thật trong phiên này:

| Bước | Bằng chứng |
|---|---|
| Engine load offline | `/health` 200: `engine=ready`, `items=118`, `cf=false`, fingerprint `{version: null (flat legacy load), manifest_sha256: 29098b37e898ad060118b96b4f66eb658ba3b93dfa5e55baa9562027458c867a}` |
| Retrieval thật | `/api/search` "docker containers": 8 hits (5014/5022/5107/5001/5021, score 83,1–89,3) |
| SSE end-to-end | `/api/chat/stream` ≈37 KB: `sources` (Docker docs thật, license Apache-2.0 ghi đúng) → không delta tạm (extractive mode) → final `generation_mode=llm_extractive`, `citation_validation.status=valid`, `cited_ids=[5013]`, `evidence_binding=verbatim`, rồi `done` |
| Engine engine-path | Frozen harness gọi trực tiếp `engine.achat_stream` 20 case, tuần tự, Qwen thật |
| CF optional gate | `/api/personas`, `/api/for-you` → 503 "cf_model.pkl không có"; search/chat/retrieval không bị ảnh hưởng |
| `/metrics` | 200, đếm route + latency TB/max |
| Direct provider smoke | Warm 18-token answer: prompt-eval 1,05s, eval 1,77s, finish `stop` |

## 5. Frozen generation evaluation — Before/After chất lượng thực đo

Dataset đóng băng: `reports/release-readiness-evidence/blind_cases.jsonl`, SHA256
`2a3a98e2d207b7c4932ced6ec87b3d7db966c8b543730545e9a76d10abe6dd1`
(20 case; AI-authored — **không phải human labels**). Chạy tuần tự, budget 45s
không đổi, không tuning, tree hiện tại:

| Đo lường | Kết quả fresh | Before cùng protocol |
|---|---|---|
| Positive accepted `llm_extractive` + citation valid | **11/12 (91,7%)** | **0/2** accepted, `citation_validation_failed` |
| Positive timeout budget | 1/12 (`blind-positive-06`, 45,2s `generation_failed`) | — |
| Elapsed (accepted), censored | p50 **38,37s**, p95 **43,88s**, min **1,54s** (prompt cache hit), n=11 | — |
| TTFT (accepted) | ≈ elapsed (không có delta tạm) | — |
| Negative không biến thành claim | **7/8**: 2 off-topic gate tức thời `template` (0,08–0,09s), 3 explicit refusal `no_selected_evidence`, 2 timeout | sim-human refusal 1/1 |
| Negative search-intent | 1/8 `extractive` 0,105s — trả excerpt OTP thật (item 5023), không claim tự do | — |

Khác biệt Before/After có hồ sơ rõ: phiên trước freeform generation gây
**counterexample hỗ trợ passage** (answer DEV5061 nói `__enter__`/`__exit__` nhưng
chunk `5061:7` không chứa các method — [spotcheck](production-blockers-evidence/citation-support-spotcheck.json)).
Tree hiện tại mặc định chuyển semantic-chat sang **extractive evidence binding**:
1) model chỉ chọn chunk ID bằng JSON schema enum; 2) engine tự tái dựng câu trả
lời từ excerpts đã lưu; 3) validation gắn `evidence_binding="verbatim"`.
Byte-level join-check của phiên này: **11/11 accepted answers verbatim với
stored excerpts** ⇒ "unsupported-passage citation" không còn xuất hiện trong các
câu được accepted. `semantic_grounding` vẫn `not_verified` — entailment thật và
human faithfulness chưa đo, vẫn `null` (không ước lượng từ mode mới).

## 6. System journeys thật — Web + PostgreSQL + Chrome + TLS + lifecycle

| Gate | Kết quả fresh |
|---|---|
| PostgreSQL 18.6 userspace fixture | started thành công (pg-root `LD_LIBRARY_PATH`), TCP 127.0.0.1:15432, SCRAM; không system install |
| HTTP + real DB journeys | **36/36 PASS** — register, bcrypt storage, duplicate-email reject, CSRF reject, dashboard, diagnostic/profile, progress persistence + validation, user isolation, search render, admin gate deny, non-stream chat/history/metadata, cross-user chat delete isolation, valid SSE persistence, incomplete-final-without-done không lưu, forged PDF reject, valid PDF pending + BYTEA + text extract, byte-identical owner download, pending hidden/cannot-delete, logout + auth cleared, invalid password reject, login, conversation listing |
| Chrome thật (fresh profile) | **9/9 PASS** — login sau DB restart, progress sau restart, persisted chat render, real SSE persist + completes, reload confirm, final-without-done không hoàn thành browser, invalid-UTF8 không hoàn thành, final+done completes, no uncaught exceptions |
| Backup/restore | PASS — pg_dump `itlr_fixture` → restore `itlr_restored`; 15 bảng row-count + SHA256 fingerprint bằng; cluster fast-restart preserves data (drill prior PASS lặp lại nguyên trạng) |
| TLS smoke | PASS — TLSv1.3 với verified certificate (SAN 127.0.0.1), `/login` 200, CSP/nosniff; HSTS absent đúng NODE_ENV=test |
| Artifact lifecycle | PASS — trusted copy integrity (2 versions), pointer a→b, E5 engine thật 118 items + retrieval, `_reload_engine` b, rollback về a, **tamper rejection**, failed switch giữ pointer trước |
| Dọn dẹp | Web 18030 + upstream fixture 18031 được dừng theo `service-pids` với verify cmdline; ports kiểm closed; PG data fixture giữ nguyên |

Phạm vi: browser protocol dùng upstream fixture cho SSE — không sống-Qwen;
sống-Qwen đã có ở §4/§5. Mobile/desktop 390px vs 1280px không re-run trong phiên
(inherited PASS từ [full-system audit](FULL_SYSTEM_AUDIT_2026-10-30.md)); không
trình bày như bằng chứng mới của phiên này.

## 7. Bottlenecks và gates còn mở

1. **Uncached full prompt không hoàn tất trong 45s** — tái hiện lần nữa: nonce
   prefix ~6k chars, trực tiếp Ollama non-stream, không complete ở
   **60,07s** (client cap 60s > request budget 45s). Root cause là prefill
   throughput CPU (~34 tok/s decode-pre-eval quan sát từ session trước; eval
   speed vẫn ~10 tok/s), hardware-bound trên i7-8650U CPU-only; không phải bug
   code. Budget và context không nới (đúng protocol). Warm/cache-hit request
   hoàn tất 0,35s. Mitigation hợp lệ duy nhất nằm ở hạ tầng (CPU mạnh hơn /
   model nhỏ hơn), nằm ngoài ràng buộc "không thay model" của phiên.
2. **Docker production staging BLOCKED** — `docker.sock` `root:docker 0660`,
   user không trong group, `sudo -n` chỉ ra "interactive authentication is
   required", thiếu `newuidmap`/`newgidmap`/`slirp4netns`/`fuse-overlayfs` cho
   rootless. Preflight transcript đầy đủ ở
   [evidence](final-e2e-evidence/docker-preflight.txt). Compose/Caddy/migration/
   backup drill trong Docker vẫn chưa kiểm chứng; alternative native staging
   (PG18 + Web + Chrome + TLS + backup) đã chạy thay thế (§6).
3. **Human faithfulness/groundedness/hallucination/answer relevance = null** —
   cần reviewers độc lập; packet protocol sẵn sàng
   (`human-review-packet.jsonl`, fields null, không AI label).
4. **Model-internal cancellation ACK / capacity/soak / cold start / context
   token boundaries** — not verified; transport cancellation đã đo ở phiên trước.
5. **npm audit advisories dev-chain moderate (14)** — accepted-risk có triage;
   fix-capable hiện tại là breaking eslint downgrade → rejected rõ reason.

## 8. Tài nguyên hệ thống (quan sát trong phiên)

- RAM host khi chạy full stack: ~10/14 GiB (API+E5 ≈1,7 GiB RSS; Ollama runner
  model runtime ≈2,2 GiB trong ollama ps; peak RSS runner 2,4 GiB ghi từ phiên trước).
- `/tmp` tmpfs 7,5G (dùng ~439M); NVMe 937G (59G dùng). Không resource cạn.
- Không service người dùng bị restart: daemon 11434 giữ nguyên; TTS cổng 8000
  không đụng; E2E API dùng 18600; journeys dùng 18030/18031 riêng rồi dừng sạch.

## 9. GO/NO-GO từng gate

| Gate | Verdict |
|---|---|
| Full Python/Web test + typecheck/lint/build + coverage | **PASS** (489/146; 67,37% / 47,05%) |
| Security scans | **PASS với accepted-risk dev-only** (Bandit 0 High; pip-audit 0; npm dev-chain moderate) |
| Retrieval policy | UNCHANGED (inherited 83,33% Recall@5 frozen) |
| Generation quality (frozen AI labels) | **PASS scoped**: 11/12 positive accepted, 7/8 negative không-claim |
| Verbatim citation integrity (accepted cases) | **PASS by construction** (11/11 byte-check) |
| Semantic entailment / human faithfulness | **NOT VERIFIED** (null) |
| Web/DB/Chrome/TLS/backup/lifecycle real | **PASS** |
| Uncached 45s budget | **FAIL** (hardware prefill; không nới budget) |
| Docker production staging | **BLOCKED** (permissions; no sudo) |
| Model-internal ACK/capacity/soak/cold start | **NOT VERIFIED** |
| **Overall** | **NO-GO production** — các PASS scoped chỉ có nghĩa trong phạm vi staging thử nghiệm này |

## 10. Evidence và tái lập

- `reports/final-e2e-evidence/`: frozen harness script + raw results
  (`generation-eval.json`, `human-review-packet.jsonl`, `frozen-eval.log`),
  HTTP-DB 36 + browser 9 logs, backup/restore, TLS, artifact lifecycle, coverage
  JSON, bandit/pip-audit JSON, docker preflight transcript, SSe raw,
  npm-audit output.
- Regression: lệnh `AGENTS.md` (cloud keys unset, USE_OLLAMA=0, OMP=1) trên máy này.
- Frozen eval: `frozen_eval.py` (evidence dir), dùng `ITLR_ARTIFACTS_DIR` staging copy,
  dataset SHA asserted, budget 45s, không tuning.
- Chỉ sửa code runtime trong phiên: cập nhật assertion test stale (§2, RED→GREEN).
  Không thay model/ranking/threshold/dependencies runtime.
- Không commit/push/activation/migration được thực hiện. Historical reports giữ
  nguyên; số từ release trước không được trình bày như số chạy mới.
