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

## 11. Resume validation — evidence excerpt budget A/B và Docker staging thật (2026-10-31, phiên nối tiếp)

Phiên này chạy trên checkout `main` sạch tại `f14c428…` (working tree clean, không commit/push),
theo bộ công cụ resume ngoài repo (`LOCAL_AGENT_RESUME.md`, `compare_frozen.py`,
`run_quality_gates.sh`) và dùng chung protocol frozen. Mọi số dưới đây chạy mới;
số cũ trong §1–§10 giữ nguyên là lịch sử.

### 11.1 A/B `ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET` `None` vs `800` — quyết định REVERT

`generation-eval-budget800` cũ **không dùng được làm bằng chứng promotion**: `chatbot.py` được
sửa lúc 11:22:45, sau khi run 20 case kết thúc lúc 11:20; runner không set biến môi trường và
không có launch record, nên không chứng minh được arm. Vì vậy đã chạy A/B có kiểm soát
(`frozen_eval_ab.py`): cùng dataset SHA, cùng model, budget 45s, arm ghim trong process
(None arm monkeypatch `_evidence_char_budget`, 800 arm dùng env override), 1 warmup/arm,
`prompt_chars` ghi từng case làm bằng chứng arm.

| Đo lường | `None` | `800` |
|---|---|---|
| Positive accepted (valid + verbatim) | **11/12** | **11/12** |
| Negative không-claim | 7/8 | 7/8 |
| prompt chars p50 / max | 4926 / 5340 | 4578 / 4904 (−7,1%) |
| p50 elapsed accepted | 34,886s | 29,260s (nhiễu prompt-prefix cache: 5 case <5s) |
| Case lỗi | `positive-06` timeout `generation_failed` 45,124s | `positive-12` từ chối `no_selected_evidence` 1,322s |

Đối chiếu từng case: `positive-06` được cứu (timeout → accepted) nhưng `positive-12`
**mất** (accepted → từ chối vì evidence view bị cắt), `negative-08` đổi từ timeout 45,186s
sang từ chối thật 0,485s. Net chất lượng bằng nhau, có regression thật trên một positive mà
default đang pass; tiết kiệm prompt 7% không thể bù prefill ~30s của gate uncached.

**Quyết định:** giữ default `None` (env override vẫn dùng được) và revert promotion đang có
trong working tree. TDD: revert code khi test còn assert 800 → FAIL `ImportError` (RED);
revert test → **28 passed** (GREEN). Bản đã promote lưu ở
`/tmp/opencode/itlr-e2e/reverted-800/`, không xóa.

### 11.2 Regression và security (fresh, cùng checkout sạch)

| Gate | Kết quả | Trước (§3) |
|---|---|---|
| Python pytest | **494 PASS / 0 fail / 0 skip**, 50,65s | 489 |
| Python statements coverage | **3946/5835 = 67,63%** | 67,37% |
| Web Vitest | **146 PASS / 26 files** | 146 |
| Web line coverage | **648/1377 = 47,05%** (statements 44,24%, branches 36,15%) | 47,05% |
| typecheck / lint / build | PASS | PASS |
| compileall / pip check | PASS | PASS |
| pip-audit | **0 advisory** | 0 |
| npm audit | **0 vulnerabilities** | 14 moderate (dev-chain) |
| `npm ls minimatch` | 11.0.3 deduped, `overrides ^11.0.1` | — |
| Bandit | **0 High** / 27 Medium / 46 Low | 0/26/38 |

Gate script `run_quality_gates.sh` chạy qua `sg docker`; `docker info` PASS (server 29.9.2).
Số Web cao hơn 146 trong một số log cũ là do scope collect, không phải tăng test.

### 11.3 Docker staging fresh — PASS scoped (thay cho BLOCKED ở §7.2)

Khác với kết luận cũ "docker.sock root:root, không có quyền": user **là thành viên group
docker (gid 972)**; gọi `docker` trực tiếp trong shell phiên này bị `permission denied` vì
process không có supplementary group, nhưng `sg docker -c` hoạt động. Không dùng sudo/pkexec.

- Project cô lập `itlr-resume-1031c`, subnet `172.29.234.0/24`, ports `127.0.0.1:19081`
  (API) và `127.0.0.1:19444` (Caddy). Env/password mới, file 0600, không nằm trong repo/evidence.
- Image build **fresh `--no-cache`** từ working tree:
  `itlr-resume-1031b-api:stage` = `sha256:3dac16199c26c419362055c17032cca29d6a697c07738274fbc132f36de66a25`,
  `itlr-resume-1031b-web:stage` = `sha256:23e1a8abedd7a18cf19bd73344795183e6808cac93eeeed3c0e617daebcb12c1`.
  Reuse cho lượt tour cuối (ghi rõ, không tạo lại timestamp giả).
- Artifacts mount bản staging dùng một lần `docker-a`/`docker-b`; HF và model mount read-only;
  volume riêng theo project. Không `down -v`; sau stop volumes còn nguyên, ports đóng.
- Container: torch `2.15.0+cpu`, sklearn `1.9.1`, sentence-transformers `6.2.0`, CUDA false.

| Gate Docker | Kết quả |
|---|---|
| postgres healthy, migrate ×2, seed 3 bản ghi nguồn thật | PASS |
| `/health`: engine ready, **items=118**, fingerprint `docker-a` / manifest `29098b37…` | PASS |
| E5 search thật `/api/search` | PASS |
| SSE thật qua Web/Caddy: `sources → meta → text → final → done`, `llm_extractive`, 31,87s | PASS |
| `reload` không token → 403; reload có token → 200 | PASS |
| activate `docker-b` + reload; rollback `docker-a` + reload; **tamper bị từ chối** | PASS |
| backup/restore 15 bảng cùng row-hash; restart giữ nguyên dữ liệu; login lại sau restart | PASS |
| **Chrome thật 11/11**: CA nội bộ tin cậy, login, progress sau restart, SSE hoàn tất, reload hội thoại, cancel đóng socket provider **55ms** (UI ready 11ms), không lỗi runtime | PASS |
| Driver checks | **27/28 PASS**; check còn lại (`provider-after-cancel`) fail vì probe dùng `num_predict=8` nên `done_reason=length`; chạy lại probe đúng (`num_predict=16`) → `done=True`, `done_reason=stop`, 1,742s → PASS |
| `/api/chat/stream` cancelled không lưu partial vào PostgreSQL | PASS |

RAM trong lúc chạy: api 1,008 GiB; ollama 2,176 GiB; web 41,5 MiB; postgres 33,2 MiB;
caddy 17,5 MiB; observer 19,3 MiB; host dùng ~12,8/15,2 GB. Sau stop: ports 19081/19444 đóng.

### 11.4 Gate 45 giây — vẫn FAIL, không nới

Frozen A/B arm `None` tái hiện timeout thật: `blind-positive-06` dừng ở **45,124s** với
`generation_failed` (budget 45s, không đổi). Trong container, cùng query khi model đã warm
xong trong 38,496s (`llm_extractive`, citation valid) — không chứng minh được case uncached.
SLO 45s **không được nới**; đây vẫn là blocker hardware-bound (prefill CPU ~30s/case).

### 11.5 Verdict sau phiên nối tiếp

| Gate | Verdict |
|---|---|
| A/B prompt budget | **PASS scoped** (đo được, quyết định revert) |
| Python/Web regression + coverage + typecheck/lint/build | **PASS** (494/146; 67,63% / 47,05%) |
| Security scans | **PASS** (0 High; pip-audit 0; npm audit 0) |
| Docker staging real (PG/Caddy/E5/Qwen/Chrome/cancel/backup/restore/tamper/rollback/restart) | **PASS scoped** single-host CPU-only, disposable data |
| Uncached 45s budget | **FAIL** (host 60s trước đó; timeout 45,124s tái hiện) |
| Human faithfulness/entailment | **NOT VERIFIED** (mọi field `null`) |
| Capacity/soak/cold start/multi-host | **NOT VERIFIED** |
| **Overall** | **NO-GO production** |

Evidence: `reports/final-e2e-evidence/` (A/B JSON + log + analysis, gate logs/coverage,
`docker-resume-1031c/` gồm docker-result, browser 11 check, observer sockets, probes,
DB fingerprints, compose/Caddy/observer, `SHA256SUMS.txt`).

## 12. Final production remediation — latency SLO, human eval packet, reliability/capacity (2026-10-31)

Tiếp tục từ checkpoint §11 trên cùng checkout sạch `f14c428…`; không sửa code runtime,
không đổi model/hardware/SLO, không commit/push, không chạm active artifacts.

### 12.1 SLO 45s — benchmark thật và kết luận hardware-bound

Prompt thật của một case frozen: **4893 chars, 5 chunk, 1387 token**. Benchmark trên
Ollama 0.40.13 container cô lập (cùng model `qwen2.5:3b` Q4_K_M, `num_ctx=4096`,
`OLLAMA_NUM_PARALLEL=1`, 8 thread CPU, không đụng daemon 11434 của người dùng):

| Cấu hình | Prefill tok/s (cold) | Prefill 1387 token | Decode tok/s | Warm (prefix cache) |
|---|---|---|---|---|
| baseline | 31,2 | **44,5s** | 6,8 | 0,34s |
| `OLLAMA_FLASH_ATTENTION=1` | **34,5** | **40,2s** | 7,3 | 0,32s |
| `num_batch=256` | 34,0 | 40,8s | 13,9 | 0,32s |
| `num_thread=6` | 31,5 | 44,0s | 15,4 | 0,30s |
| `OLLAMA_KV_CACHE_TYPE=q8_0` | 26,9 | 51,5s | 7,1 | 2,97s |
| flash + KV q8_0 | 26,9 | 51,5s | 7,1 | 3,00s |

Kết luận đo được: **riêng prefill của prompt đầy đủ đã 40–51s > SLO 45s** trên CPU này;
decode chỉ cần ~10–20 token nên không phải nút cổ chai; cache hit thì 0,14s prefill /
0,34s tổng nên vấn đề đúng là request uncached. Flash attention là cấu hình miễn phí
tốt nhất (+10,6% prefill) nhưng **không đóng được khoảng thiếu ~5s + decode + retrieval**.

Prompt compression (đường có sẵn `ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET`, không sửa code):

| Arm | Positive accepted | Negative không-claim | Prompt chars p50 | p50 / max elapsed | Case hồi quy |
|---|---|---|---|---|---|
| `None` (default) | **11/12** | 7/8 | 4926 | 34,89s / 40,15s | — |
| `800` | 11/12 | 7/8 | 4578 (−7,1%) | 29,26s / 43,30s | `positive-12` accepted → `no_selected_evidence` |
| `500` | **10/12** | 7/8 | 3086 (−37,3%) | 23,99s / 33,38s | `positive-07` và `positive-11` accepted → `no_selected_evidence` |

Không arm nào đạt bar "không suy giảm chất lượng"; **default giữ `None`**. Vì vậy
SLO 45s cho prompt đầy đủ **FAIL trên hardware này**, không phải lỗi code và không được
nới SLO. Cấu hình tối thiểu cần kiểm chứng lại trên máy thật: prefill ≥ ~65–70 tok/s
(tức ~2x hiện tại) cho prompt ~1400 token, ví dụ CPU 8–12 nhân hiện đại (P-core) hoặc
GPU CUDA tầm RTX 3060/4060 trở lên; phải chạy lại frozen 20 case và đo cold/warm trước
khi tuyên bố đạt. Flash attention nên bật ở deployment nhưng không thay thế hardware.

### 12.2 Human faithfulness — packet sẵn sàng, nhãn người vẫn NOT VERIFIED

- Frozen 20 case giữ nguyên SHA `2a3a98e2…`; packet `human-review-packet.jsonl` vẫn
  `human_* = null`.
- Bổ sung `reports/release-readiness-evidence/human_eval_supplement.jsonl`
  (SHA `818e3b35…`): 20 case độc lập — 8 positive, 6 hard-negative, 3 multi-hop,
  3 prompt-injection; VI 11 / EN 9; nhãn `AI-drafted scenario (not human)`.
- `HUMAN_REVIEW_PROTOCOL.md` (SHA `f8a72a21…`): thang 0–3 cho faithfulness,
  answer relevance, citation support, refusal appropriateness; quy ước
  human / AI-drafted / heuristic / LLM-as-judge; công thức unsupported-claim rate,
  citation precision, refusal accuracy; quy trình 2 reviewer độc lập + trọng tài.
- Chưa có người chấm → unsupported-claim rate, citation precision, refusal accuracy,
  human faithfulness = **null / NOT VERIFIED**. Proxy máy (11/11 accepted byte-verbatim,
  7/8 negative không tạo claim) chỉ là `heuristic`, không phải entailment.

### 12.3 Reliability/capacity trên staging (single-host, volumes giữ)

| Phép đo | Kết quả |
|---|---|
| Cold start → `/health` ready | **42s** |
| Request chat cold đầu tiên (conc 1) | **40,25s**, terminal `done`, 118 items |
| Concurrency 2 (chat, cache warm) | max 4,13s, 0 lỗi |
| Concurrency 4 (chat, cache warm) | max 9,16s, 0 lỗi (xếp hàng vì 1 LLM worker) |
| Concurrency 8 (search) | 1,69–1,84s/request vs 0,28s đơn lẻ (~6x) |
| Soak 120s | 89 vòng, 45 chat **tất cả terminal `done`**, p50 2,22s, max 3,56s (cache warm) |
| Cancel giữa stream (client đóng) | dừng sau `sources`,`meta`, **không** có `final/done`; health sau đó 5ms |
| Crash recovery (kill -9 api → up) | **1s** tới healthy; DB counts trước/sau giống hệt (users 1, messages 8, conversations 4, courses 3) |
| RSS | api 921 MiB → 1,125 GiB trong lúc tải; ollama 2,135 → 2,164 GiB; web 27–56 MiB |

Giới hạn: soak ngắn và lặp cùng query nên chủ yếu đo cache-warm; chưa có soak dài,
cold concurrency >1, hay multi-host. Throughput cold xấp xỉ **1 request/40s/worker**;
capacity thực tế cần thêm worker/hardware. Không suy diễn single-host thành HA.

### 12.4 Gates sau remediation

Không có thay đổi code runtime trong phần này (chỉ thêm evidence/tài liệu), nên các
gate §11.2 vẫn là lần chạy mới nhất trên cùng cây: **494 Python / 146 Web PASS**,
coverage **67,63% / 47,05%**, pip-audit 0, npm audit 0, Bandit 0 High, typecheck/lint/build PASS.

### 12.5 Verdict cập nhật

| Gate | Verdict |
|---|---|
| SLO 45s với prompt đầy đủ trên CPU hiện tại | **FAIL** (prefill cold 40–51s; compression 500/800 regress) |
| Latency benchmark cold/warm/uncached + config sweep | **PASS** (đo được, có kết luận) |
| Human faithfulness/entailment | **NOT VERIFIED** (`null`, packet + protocol sẵn sàng) |
| Reliability: cold start, restart, cancel, crash recovery, DB integrity | **PASS scoped** single-host |
| Capacity: concurrency 1/2/4 chat + 8 search, soak 120s | **PASS scoped**; soak dài/multi-host **NOT VERIFIED** |
| Docker staging E2E (§11.3) | **PASS scoped** |
| Security/regression | **PASS** |
| **Overall** | **NO-GO production** — blocker chính: SLO 45s hardware-bound + human labels |

Ưu tiên xử lý: (1) hardware/GPU đạt prefill ≥65–70 tok/s và chạy lại frozen + cold/warm;
(2) human panel chấm 2 bộ packet; (3) soak dài + cold concurrency + multi-host; (4) bật
flash attention ở deployment khi phần cứng đã đạt.

Evidence: `reports/final-e2e-evidence/bench-latency/` (sweep, prompt, `latency-summary.json`),
`generation-eval-ab-{none,800,500}.json`, `reliability-load/` (load.py, tour logs,
conc/soak/cancel/RSS/DB JSON, `reliability-summary.json`), `docker-resume-1031c/`,
`SHA256SUMS.txt`.
