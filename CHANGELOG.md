# ITLR–RAG | Intelligent IT Learning Platform — Changelog

## Final release hardening: host PG, host Ollama, model pull, human gap — 2026-10-31

- Native với PostgreSQL host: kết nối DB `itlr_web`, catalog 0→**178** bằng sync thật
  (users/messages giữ nguyên), Web native course 200/404 + dashboard, restart giữ DB/session.
  Write E2E trên DB người dùng **BLOCKED** (không có quyền tạo DB; tránh ghi dữ liệu thật).
- Docker host-Ollama override: PASS qua Ollama bind `0.0.0.0:11435` + host-gateway.
- Docker tải model mới: pull `qwen2.5:3b` 1.9GB vào volume, chat `llm_extractive` PASS.
- Docker logout/CSRF: 403 thiếu CSRF, logout 302, dashboard về login PASS.
- Human faithfulness: 40 case, rubric 0–3, 0 reviewer → **NOT VERIFIED** (không điểm giả).
- Gates: 510 Python / 166 Web, coverage 68,27% / 52,41%, security 0.
  [Report](reports/FINAL_RELEASE_READINESS.md). Production **NO-GO**.

## Dual-mode E2E + artifact override fix — 2026-10-31

- Chạy thật cả Native (uvicorn + node, PostgreSQL 16 container, Qwen host) và Docker full
  stack với 178 item thật: register/login, course 200/404, search, chat SSE
  `llm_extractive` + citation valid, persistence, cancel không lưu partial, restart Docker giữ DB.
- Fix root cause: `ITLR_ARTIFACTS_DIR` trỏ root có `CURRENT.json` bị dùng trực tiếp → API 503
  VersionError. Nay tự resolve version; staging phẳng vẫn dùng trực tiếp. Test RED→GREEN.
- Gates: **510 Python / 166 Web PASS**, coverage 68,27% / 52,41%; security 0.
  [Dual-mode report](reports/FINAL_DUAL_MODE_E2E.md). Production vẫn NO-GO.

## Observability profile + final engineering pass — 2026-10-31

- Thêm metrics Prometheus cardinality thấp cho API/Web (route template, mode, status, provider,
  artifact version), endpoint `/metrics/prometheus` (admin token hoặc Bearer) và `/metrics` Web
  (token/loopback); instrument search, chat/SSE (TTFT, tokens, citation, outcome).
- OTel tracing opt-in (`OTEL_EXPORTER_OTLP_ENDPOINT`) cho `http.request`, `retrieval.search`,
  `generation.chat`, `sse.chat`, `crawler.run`, `index.build`; no-op khi tắt.
- Compose profile `monitoring`: Prometheus + Grafana + Loki + Tempo + otel-collector + cAdvisor
  + node-exporter + postgres-exporter + promtail; dashboard 13 panel, 10 alert, retention/volume/
  loopback; footprint đo **~383 MiB RAM**.
- README: Docker full stack, Windows WSL2/Ubuntu, monitoring walkthrough, troubleshooting.
- Gates: **508 Python / 166 Web PASS**, coverage 68,22% / 52,41%; pip-audit/npm audit 0,
  Bandit 0 High. Production vẫn NO-GO (cold SLO 45s, human).

## Pipeline audit: catalog export/verify, source-link audit, 404 root cause — 2026-10-31

- Root cause 404 khi bấm khóa học: PostgreSQL Web chưa refresh sau khi build index (CSV
  no-clobber + pipeline không export/sync). Kiểm chứng thật: trước sync `/courses/5129` → 404,
  sau `npm run sync` → 200, id không tồn tại → 404.
- `export_web_catalog.py --refresh` (merge giữ row cộng đồng, ghi atomic), thêm
  `scripts/verify_web_catalog.py` và `scripts/audit_source_links.py`; `refresh_pipeline.py`
  tự export + verify sau build, `--sync-web` chạy `npm run sync`.
- `appendCatalogRow` cấp id theo max, tránh ghi đè khóa học thật.
- 9 test Python + 1 test Web mới. Gates: **503 Python / 163 Web PASS**, coverage
  67,63% / 51,45%; pip-audit 0, npm audit 0, Bandit 0 High. Production vẫn NO-GO.

## Final codebase freeze: dead-code cleanup, gates, freeze verdict — 2026-10-31

- Bỏ 1 import không dùng (`itlr/collect/normalize.py`), đổi 2 tham số không dùng thành `_req`;
  tsc strict unused sạch. Không xóa file, không đổi dependency/API/schema/model/ranking.
- Gates: 494 Python / **160 Web** PASS, coverage 67,63% / 51,42%; typecheck/lint/build,
  pip-audit 0, npm audit 0, Bandit 0 High, secret scan 0.
- [FINAL_CODEBASE_FREEZE](reports/FINAL_CODEBASE_FREEZE.md): **CODE FREEZE READY**,
  **PRODUCTION NO-GO** (cold SLO 49,80s, human faithfulness `null`).

## Final release hardening: business rules, cold/warm benchmark, human packet — 2026-10-31

- Xóa lesson **đã duyệt** chỉ admin (contributor không thể rút nội dung khỏi người học).
- `POST /account/logout-all` tăng `token_version` để thu hồi JWT trên mọi thiết bị; `/logout`
  vẫn chỉ xóa cookie thiết bị hiện tại.
- `/forgot` dọn reset token hết hạn/đã dùng >1 ngày (giữ bảng không phình).
- Benchmark cold/warm tách thành phần: cold 49,80s (load 6,21 + prefill 43,42s @31,9 tok/s),
  warm 0,33s; retrieval p50 145ms; stream warm p50 3,69s / max 32,61s. **SLO 45s vẫn FAIL.**
- Human packet: thêm `human_review_scoring_sheet.csv` (40 case, cột người chấm để trống).
- Gates: 494 Python / **160 Web** PASS, coverage 67,63% / 51,42%; pip-audit **0** (chạy lại);
  npm audit 0; Bandit 0 High; PG16 fresh/re-apply/legacy/rollback PASS; Chrome 11/11; cancel 78ms.
- [FINAL_RELEASE_READINESS](reports/FINAL_RELEASE_READINESS.md). Verdict **NO-GO** (SLO, human).

## Security/correctness audit: lesson progress, reset transaction, JWT revocation — 2026-10-31

- Lesson chưa duyệt không còn complete được và không bị tính vào progress; progress chỉ đếm
  lesson `approved`, tính bằng một câu SQL nguyên tử (hết race read-modify-write).
- Approve/delete lesson đồng bộ lại enrollment cho **mọi** người học bị ảnh hưởng.
- Reset mật khẩu chạy trong transaction (claim token + đổi mật khẩu + thu hồi session).
- JWT bị thu hồi sau đổi/reset mật khẩu bằng `users.token_version` (ALTER idempotent).
- Reset email có cooldown theo tài khoản (mặc định 60s) và chỉ giữ token mới nhất.
- Không đổi API/RAG model/threshold/prompt. **494 Python / 157 Web PASS**, coverage
  67,63% / 50,67%; npm audit 0, Bandit 0 High; pip-audit BLOCKED (PyPI timeout) lượt này.
- [FINAL_PRODUCTION_AUDIT](reports/FINAL_PRODUCTION_AUDIT.md). Verdict **NO-GO** (SLO 45s, human).

## Documentation rewrite: bộ tài liệu kỹ thuật hiện hành — 2026-10-31

- Viết lại `README`, `docs/ARCHITECTURE.md`, `AGENTS.md`, `CONSTRAINTS.md`, `deploy/DEPLOY.md`,
  `deploy/PRODUCTION.md`, `deploy/LOCAL_MODELS.md`; thêm `docs/RAG.md`, `docs/API.md`,
  `docs/TESTING.md`, `docs/EVALUATION.md`, `docs/SECURITY.md` và
  [ADR-013](docs/decisions/ADR-013-evidence-excerpt-budget.md).
- Sửa thông tin lỗi thời: Docker/HTTPS/backup không còn "NOT VERIFIED" chung chung mà ghi
  **PASS scoped** single-host; `/health` đã có fingerprint artifacts; bỏ mô tả "chưa có
  loaded-version evidence"; gom cấu hình về một nguồn ([DEPLOY](deploy/DEPLOY.md)).
- Không đổi code runtime, schema, test hay evidence. Số liệu giữ nguyên: 494 Python /
  146 Web PASS, coverage 67,63% / 47,05%, pip-audit 0, npm audit 0, Bandit 0 High, SLO 45s
  FAIL trên CPU, human faithfulness `null`, verdict **NO-GO**.

## Final remediation: latency SLO benchmark, human packet, reliability soak — 2026-10-31

- Benchmark inference thật (container cô lập, cùng model): prefill prompt 1387 token cold
  **40–51s** (27–34,5 tok/s); flash attention **+10,6%**, KV q8/batch lớn chậm hơn; cache
  hit 0,14s. Prompt compression `800` (11/12, mất `positive-12`) và `500` (10/12, mất
  `positive-07`,`positive-11`) đều regress → **giữ default `None`**. SLO 45s **FAIL**
  trên hardware này; cần prefill ≥65–70 tok/s (CPU mới/GPU) để kiểm chứng lại.
- Human eval: thêm `human_eval_supplement.jsonl` (20 case: hard negatives, VI/EN,
  multi-hop, prompt injection) và `HUMAN_REVIEW_PROTOCOL.md` (thang 0–3, quy ước nhãn,
  công thức chỉ số). Không có người chấm → `human_* = null`, **NOT VERIFIED**.
- Reliability staging: cold start 42s, cold chat 40,25s, conc 2/4 max 4,13/9,16s,
  search conc 8 ~1,7s, soak 120s 45/45 terminal `done`, cancel không phát final,
  crash recovery 1s, DB counts không đổi; soak dài/multi-host **NOT VERIFIED**.
- Không sửa code runtime; gates §11 vẫn là 494 Python / 146 Web PASS. Verdict **NO-GO**.

## Resume validation: char-budget A/B, Docker staging thật, gate 45s vẫn mở — 2026-10-31

- A/B có kiểm soát `ITLR_EVIDENCE_EXCERPT_CHAR_BUDGET` `None` vs `800` trên frozen 20 case
  (cùng SHA/model/budget 45s, arm ghim trong process, prompt chars ghi từng case):
  cả hai 11/12 positive accepted và 7/8 negative không-claim; prompt giảm 7,1%
  nhưng `positive-12` regress (accepted → `no_selected_evidence`). **Default giữ `None`**,
  promotion đang có trong working tree được revert bằng RED→GREEN (28 tests).
- Fresh gates: **494 Python / 146 Web PASS**, coverage **67,63% / 47,05%**; typecheck,
  lint, build, compileall, pip check PASS; pip-audit **0**, npm audit **0**, Bandit 0 High.
- Docker staging **PASS scoped** lần đầu chạy được trên máy này qua `sg docker`
  (user thuộc group docker; không cần sudo/pkexec): project cô lập, ports 19081/19444,
  image `--no-cache` (`api 3dac1619…`, `web 23e1a8ab…`), PostgreSQL 16 + Caddy TLS nội bộ
  + E5 + Qwen thật SSE + Chrome 11/11 (cancel đóng socket provider 55ms) + backup/restore
  15 bảng + tamper reject + reload/rollback + restart. Volumes giữ, ports đóng sau stop.
- Gate uncached 45s **vẫn FAIL** (frozen eval timeout 45,124s; không nới SLO);
  human faithfulness/entailment vẫn **NOT VERIFIED**. Verdict **NO-GO** production.
- [Certification §11](reports/FINAL_E2E_CERTIFICATION.md), [validation](reports/VALIDATION.md),
  evidence + `SHA256SUMS.txt` trong `reports/final-e2e-evidence/`.

## Evidence-bound extractive generation & readiness fingerprint — 2026-10-31

- Semantic chat có chunk retrieval mặc định dùng chế độ `llm_extractive`: model chọn
  chunk bằng JSON schema enum, engine trả quote nguyên văn từ excerpt đã lưu; câu
  không thể bind bị loại `insufficient_evidence` thay vì trả claim chưa kiểm chứng.
  SSE chỉ phát final text; citation_validation thêm `evidence_binding`.
  Frozen blind eval (dataset SHA `2a3a98e…`): 11/12 positive accepted valid và
  byte-verbatim 11/11 join-check PASS; negative 7/8 không trở thành claim.
- `/health` và `/admin/reload` thêm fingerprint artifacts đã load
  (`version` + `manifest_sha256`); readiness nhận diện snapshot đã verified,
  chỉ đổi sau reload thành công; failed reload giữ nguyên fingerprint cũ.
- Fresh full verification: **489 Python / 146 Web PASS**, coverage **67,37% / 47,05%**,
  typecheck/lint/build/compileall/pip check/pip-audit(0) PASS; Bandit 0 High,
  npm audit chỉ advisory dev-chain moderate. Endpoint + journeys thật: HTTP/DB 36/36,
  Chrome 9/9, backup/restore 15 bảng, TLSv1.3 smoke, artifact lifecycle 9/9 PASS.
- Uncached full prompt vẫn FAIL ~60s (prefill CPU-bound tại provider); Docker
  staging vẫn BLOCKED vì docker.sock quyền root:root, sudo noninteractive bị từ chối.
  Human faithfulness/remaining quality gates chưa có; verdict **NO-GO** cho production.
- [E2E certification](reports/FINAL_E2E_CERTIFICATION.md).

## Production blocker remediation — 2026-10-31

- API SSE dùng async transport và explicit cleanup; Browser Stop đóng socket Qwen
  thật khoảng64–77ms, không lưu partial output. Giữ sync APIs/V2/V3/pickle/schema.
- Async Ollama có total generation deadline và strict fragmented UTF-8 decoding;
  regression RED → GREEN, thêm7 TCP/ASGI tests và5 mocked SDK compatibility tests.
- **457 Python / 145 Web PASS**, coverage **67,24% / 46,55%**; không thêm dependencies.
  Uncached45s timeout và unsupported-passage citation vẫn tái hiện. Không đưa
  context-cut experiment vào runtime vì quality giảm. Docker/human gates chưa đạt.
- [Production blockers report, NO-GO](reports/PRODUCTION_BLOCKERS_RESOLUTION.md).

## Release validation — 2026-10-30

- UI chỉ render final và đổi conversation sau khi parser xác nhận stream hoàn chỉnh;
  lỗi EOF/UTF-8 không còn bị success flag che. Regression và Chrome thật PASS.
- PDF worker đưa Uint8Array cho parser; PDF hợp lệ từ HTTP500 → 200, giữ validation
  và resource limits. Real parser regression RED → GREEN.
- **445 Python / 145 Web PASS**, coverage **66,70% / 46,55%**. PostgreSQL18 isolated
  HTTP/DB, backup/restore, Chrome và E5 artifact lifecycle đã kiểm chứng.
- New source-disjoint AI-authored evaluation Recall@5 83,33%, không tuning.
  Generation reliability và production deployment vẫn **NO-GO**;
  [release evidence](reports/RELEASE_READINESS_FINAL.md).

## Production hardening và engineering review — 2026-10-30

- Calibrate search default 90 → 84 trên frozen dev data; giữ explicit thresholds,
  off-topic gate và ranking weights. Không rewrite query nếu không có correction;
  chỉ glossary-expand bare aliases. Có holdout/source-disjoint confirmation metrics.
- Web yêu cầu final/done hoàn chỉnh trước khi lưu history; từ chối stream dở dang,
  giới hạn message/context phù hợp FastAPI, giữ dữ liệu DB và Unicode.
- Sửa JSON NaN metadata trong recommendations; không gửi full snapshot bodies.
  Ollama có elapsed budget tại event boundaries, không nới completion validation.
- Atomic re-pickle giữ file gốc khi lỗi và không restamp sklearn mismatch; bỏ filter
  che version warning. Xóa preparation work không dùng, gom Ollama request payload.
- **445 Python / 140 Web PASS**, coverage **66,70% / 46,48%**. Không commit/push,
  schema change hoặc activation. [Engineering review và NO-GO](reports/FINAL_ENGINEERING_REVIEW.md).

## Full-system audit Linux local — 2026-10-30

- Ollama giữ model được chỉ định, kiểm tra non-stream completion, dùng history
  budget ở cả hai chế độ và tôn trọng `OLLAMA_TIMEOUT` đã ghi trong runbook.
  Regression có RED → GREEN; thiếu model/lỗi local không chuyển provider.
- Vitest dùng credentials fixture cô lập, chạy được khi không có `web/.env`;
  runtime vẫn yêu cầu credentials riêng. Bỏ quảng cáo 50.000 tài nguyên không có căn cứ.
- Sửa first-probe integrity mismatch: tạo `.activation.lock` trước manifest SHA256;
  giữ kiểm tra hash đầy đủ. Real E5 staging 118 items/1576 chunks probe PASS.
- Neural benchmark cho thấy recall thấp ở floor mặc định 0,90; giữ threshold và
  ghi NO-GO chờ calibration độc lập, không tối ưu điểm bằng thay nhãn hoặc bỏ gate.
- Fresh: 431 Python PASS/0 skip, coverage 66,13%; 132 Web PASS, lines 45,31%.
  Đã chạy E5/Qwen thật và Chrome public forms; không migration, activation, commit/push.
  [Bằng chứng và giới hạn production](reports/FULL_SYSTEM_AUDIT_2026-10-30.md).

## RAG quality và release validation — 2026-10-30

- Thêm 23 frozen queries/evidence trên 118 snapshot thật và evaluator tái lập K=1/5/10,
  latency/throughput/whole-process RSS; so sánh lexical với MMR. Nhãn engineer-authored,
  chưa exhaustive/human-independent; chưa đủ bằng chứng đổi ranking hoặc threshold.
- Giữ tương thích stream thiếu finish metadata nhưng log `completion unverified`,
  có regression FAIL → PASS. Sửa mô tả `/health`: chưa có loaded-version fingerprint.
- Bổ sung staging acceptance/restore drill cô lập, chưa thực thi vì thiếu môi trường.
- Fresh: **414 Python PASS/0 skip**, coverage **65,73%**; **132 Web PASS**, lines **45,31%**.
  Typecheck/lint/build/compileall/pip check PASS; online dependency audits 0 advisory;
  Bandit còn 27 Medium/47 Low, 0 High. [Release verdict: NO-GO](reports/RELEASE_VALIDATION_2026-10-30.md).

## Final architecture hardening — 2026-10-30

- Sửa bốn lỗi có regression FAIL → PASS: finish reason không hoàn tất bị coi là thành
  công; SSE nhận event sau done; Ollama bỏ qua JSON/error/EOF không hợp lệ; response
  prewarm không được đóng. Không retry lại phần text đã phát.
- Bổ sung kiểm thử history, strict fallback, cancellation và authorization order/denial.
- Fresh: **410 Python PASS/0 skip**, coverage **65,71%**; **132 Web PASS**, lines
  **45,31%**. Online pip-audit (88 distributions) và npm audit: không advisory;
  Bandit **0 High / 27 Medium / 47 Low**, chưa phải scanner sạch.
- Sửa mô tả Markdown trong ADR-009 và cập nhật contracts streaming. Production **NO-GO**;
  [bằng chứng và triage](reports/RESTRUCTURING_CONTINUATION_2026-10-30.md).

## Enterprise refactor continuation — 2026-10-30

- Tách display formatting sang `itlr/core/display.py`, giữ export cũ từ recommender;
  tách history/fallback adapter sang `itlr/chatbot/llm_adapter.py`, giữ import và call
  points cũ của chatbot. Không đổi ranking hoặc provider transport.
- Tách Web chat HTTP/SSE handlers sang `web/src/routes/chat.handlers.ts`; router giữ
  URL, authorization và thứ tự middleware. Bỏ bốn unused imports đã xác minh.
- Viết lại README, tách trạng thái hiện hành khỏi nhật ký memory, chuẩn hóa 11 ADR;
  rà 51 Markdown tracked và hai báo cáo checkpoint bổ sung. Giữ số liệu lịch sử.
- Fresh: **387 Python PASS/0 skip**, coverage statements **65,01%**; **124 Web PASS**,
  line coverage **45,01%**; typecheck/lint/build/compileall/pip check PASS.
  [Inventory và Before/After](reports/RESTRUCTURING_CONTINUATION_2026-10-30.md).
  Mermaid render và staging production chưa kiểm chứng; **NO-GO**.

## Portability, security và dedup — 2026-10-30

- Xóa API key thật khỏi `.env.example` working copy; thêm test chặn secret trong mọi env example.
- Sửa chuẩn hóa URL crawler: default port theo scheme, từ chối credential (regression FAIL → PASS).
- Bỏ `javascript:` bị CSP chặn; gom HTTP Range vào một helper; log fallback recommender;
  validate scheme `course.link` và base URL LLM; passcode admin constant-time và chặn
  open redirect qua `Referer`.
- Thêm benchmark lexical trên 118 tài liệu thật + 8 qrels một annotator; thêm test CSRF,
  admin cookie, passcode và upload-negative.
- `bench_chunks_v3` không còn phụ thuộc `resource`; test API/lifecycle dùng stub encoder
  thay vì import torch; `locking`/`versioning` có fallback Windows.
- Xử lý 20 ESLint warning (`any` → type hẹp), assert trong thư viện → exception.
- Windows: **384 Python pass/0 skip** (coverage 64,96%), Web **124 pass/25 files**
  (lines 45,01%), typecheck/build PASS, lint 0 warning; Bandit 0 High (31 Medium/61 Low),
  npm audit/pip-audit sạch. Docker/PostgreSQL/HTTPS/neural **chưa xác minh**.
  [Báo cáo](reports/AUDIT_PORTABILITY_2026-10-30.md).

## Audit continuation — 2026-10-30

- Reject timeout LLM không hữu hạn/không dương bằng LLMError.
- Sửa suffix/open/oversized/malformed/unsupported video Range ở post và message; giữ kiểm quyền.
- Regression FAIL → PASS; 339 Python và 94 Web tests PASS. Release gates deployment và human RAG còn thiếu.

## Chưa phát hành — 2026-10-30: regression-safe audit increment

- Chặn chunk vượt bound từ tail merge/overlap; sửa zero overlap và validate limits.
- Tái dùng query vector trong một semantic chat request, giữ API legacy và điểm cosine.
- Giữ filters; sửa tháng đảo chiều, graph hết cạnh, regex top và empty roadmap.
- Artifacts integrity lỗi trả 503; admin token bytes comparison và rate-limit ADMIN.
- CF builder từ chối manifest-bearing destination, pin input/output cùng directory;
  reranker init thread-safe và log fallback; thêm row_id, giữ key row cũ.
- Export catalog không ghi đè file hiện hữu chứa community uploads.
- Sửa LLM numeric env parsing trả LLMError; clamp oversized HTTP Range end ở hai route media.
- Full Python **329 pass/0 skip**, Web **78 pass**; typecheck/build PASS, lint 0 lỗi/20
  cảnh báo, npm audit/pip-audit không có advisory đã biết, Bandit 0 High (28 Medium/57 Low).
  [Bằng chứng và công việc còn lại](reports/AUDIT_INCREMENT_2026-10-30.md).

## 2026-10-30 - Verified architecture increment

- Separate offline answer presentation from chatbot orchestration while preserving existing helper imports and Markdown output.
- Fix upload append for provenance catalogs: use the same 10/16-column contract as PostgreSQL sync; reject unsupported headers before writes.
- Log streaming generation failures consistently and remove redundant console fallback branches.
- Add template characterization, catalog regression and Web HTTP health/readiness tests.
- Actual results and release blockers: [architecture checkpoint](reports/ARCHITECTURE_REFACTOR_2026-10-30.md).
- Serialize catalog CSV appends and recompute the last ID inside the write queue; the documented single-worker limit remains.

## 2026-10-30 - Deployment preparation and process boundaries

- Add an opt-in production Compose stack with HTTPS proxy, private Web/API/PostgreSQL and persistent volumes.
- Keep credentials outside Git; document release jobs, backup/recovery and coordinated index/catalog rollback.
- Separate Express composition (`app.ts`) from process lifecycle (`server.ts`); add bounded SIGTERM draining.
- Container startup now serves traffic only: migration/catalog sync must run explicitly before launch.
- Runtime verification deferred at user request; no cloud deployment or new dependency installation.

## 2026-10-30 - SSE transport hardening

- Server and browser reject malformed UTF-8 and incomplete code points at EOF.
- Browser checks complete frame size before JSON parsing and event delivery.
- Regressions reproduced RED -> GREEN; see [checkpoint](reports/PRODUCTION_CHECKPOINT_2026-10-30.md).

## Chưa phát hành — 2026-10-30: correctness và tài liệu sản phẩm

- V3: Top-K không bị cắt ngầm ở 32; tìm tài nguyên loại trùng item trước giới hạn ứng viên;
  truy hồi bằng chứng vẫn giữ nhiều chunk. Cosine được chặn trong [-1, 1], so ngưỡng với sai số float32.
- Hybrid: RRF đếm một tài liệu một lần trong mỗi ranking; pipeline tái sử dụng điểm nền đã tính.
- Evaluation: dùng retrieval model của engine đã nạp, hoạt động khi không có CF; đóng file LTR sau đọc.
- Probe: truyền đường dẫn staging qua môi trường, kiểm tra cả exit code và sentinel.
- Web: chặn redirect có backslash; quyền user được lấy từ database hiện tại sau xác minh JWT.
- Crawler: đồng bộ policy/provenance khi cập nhật; không tái sử dụng full text đã bị thu hồi trong lần
  export tiếp theo. Listing/article không phải 2xx bị từ chối; redirect kiểm robots và rate-limit mỗi hop.
- Viết lại toàn bộ Markdown tracked theo thương hiệu thống nhất; giữ số liệu và phạm vi lịch sử,
  phân biệt implemented/verified/experimental/planned. Không thêm giấy phép hay dịch vụ memory ngoài.
- Kết quả thực chạy và giới hạn triển khai: [Validation](reports/VALIDATION.md).
  Thu hồi policy không sửa artifacts đang active; cần rebuild, probe và activate có kiểm soát.


## 2026-10-30 — BM25 và đóng gói Web (checkpoint lịch sử)

- Sửa BM25 refit, thêm inverted postings và hỗ trợ pickle cũ; ngăn race công bố postings dở.
- Build Web đóng gói EJS/public/schema; bỏ copy trùng trong Dockerfile.
- Viết lại hướng dẫn hiện hành quanh web3000/PostgreSQL/API8000, không yêu cầu Claude-Mem.
- Rà soát Markdown, gắn ngữ cảnh lịch sử, sửa nhãn mô phỏng và kiểm tra local links.
- Bỏ khai báo MIT của package, giữ thông báo bản quyền bên thứ ba.
- Kiểm chứng cuối:260 Python pass/0 skip,59 Web pass; build/typecheck/wheel/links pass,lint20 cảnh báo cũ.
- Bằng chứng, benchmark và giới hạn xem reports/VALIDATION.md.

## Phạm vi lịch sử


Các mục dưới ghi trạng thái tại thời điểm thay đổi, không phải chứng nhận runtime hiện tại.
Phiên bản package hiện vẫn là `1.0.0`; tiêu đề `2.0.0` bên dưới là nhãn lịch sử, không xác nhận một release tag.
Bằng chứng mới nhất: [Validation](reports/VALIDATION.md).

Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.0.0] - 2026-10-29

## Added — dữ liệu thật + vận hành (crawling & versioned index)
- **Crawler Python** (`itlr/collect/`): `http.py` (HTTPX + retry exponential-backoff,
  robots.txt + Crawl-delay, rate-limit per-host), `extract.py` (chọn content theo mật độ
  `_pick_main`, chống listing-junk), `sources.py`/`adapters.py` (JSON API · RSS · HTML
  listing; `link_pattern` lọc trang mục lục VnExpress), `store.py` (SQLite docs + item_map
  item_id ổn định), `quality.py` (too_short/dup/hash), `chunk.py` (900 chars/overlap 120),
  `runner.py` (lượt chạy + tổng kết `last_run.json`), `normalize.py` (schema ITLR +
  chống trùng legacy, provenance `origin/crawl_license/crawl_lang/crawl_hash`).
- **`scripts/collect_data.py`** — crawl CLI: `--sources`,`--stats-only`,`--verbose`;
  lượt đầu: 85 docs (devto 25 · fCC 10 · MDN 25 · VnExpress 25 snippet-only).
- **`scripts/build_all_v2.py`** — catalog V2 (legacy 5000 + crawl thật, item_id từ 5001)
  → build staging → probe 3 mức → activate nguyên tử → GC keep=3; `--dry-run`,
  `--no-activate`, `--no-probe`, `--with-cf`, `--online`, `--max-items`.
- **`scripts/refresh_pipeline.py`** — cron entry một lệnh (crawl → build nếu có docs mới;
  mọi nguồn lỗi ⇒ không build).
- **Index phiên bản hóa** (`itlr/versioning.py` + `itlr/indexv2.py`): `versions/<id>`,
  MANIFEST probe, `CURRENT.json` ghi nguyên tử, `rollback()`, `garbage_collect(3)`;
  con trỏ được `itlr.config.current_dir()` re-read mỗi lần gọi — engine thấy version mới
  khi restart/reload.
- **Embeddings V2** (`itlr/pipelines/build_embeddings_v2.py`): encode TỪNG CHUNK
  (max 900/overlap 120), vector item = mean + L2 → giữ hợp đồng 1 hàng ↔ 1 item;
  thêm `chunk_meta.pkl`; ANN/faiss + char n-gram như cũ.
- **API admin có token** (`itlr/api/server.py`): `/admin/reload` đòi
  `X-Admin-Token` khớp env `ITLR_ADMIN_TOKEN`; env trống ⇒ 403 (fail-closed).
- **CF thành tùy chọn** (`itlr/engine.py`): thiếu `cf_model.pkl` ⇒ log WARNING, engine
  chạy bình thường; `/api/personas`,`/api/for-you` trả 503 (`CFUnavailable`);
  `/health` và `/admin/reload` báo `"cf": true|false`.
- **`eval/eval_v2_real.py`** — số đo thực trên index active: Recall@5/10, MRR@10,
  NDCG@10 (qrels rule-based, đánh dấu trung thực), latency p50/p95, citation accuracy.
- **Deployment**: `Dockerfile` (healthcheck, smoke-import, var/ volume),
  `docker-compose.yml` (api + refresh profile), `bin/refresh_env.sh`,
  `deploy/DEPLOY.md` (cron + systemd service/timer + rollback + giám sát).
- **Docs**: ADR-005 (CF optional), ADR-006 (nguồn/licensing/robots), ADR-007
  (versioning), ADR-008 (admin token); README phần V2 + sơ đồ build.
- **Tests mới** (+21): `test_collect_utils.py`, `test_http_layer.py`,
  `test_versioning.py`, `test_collect_crawl.py`, `test_collect_runner.py`,
  `test_normalize.py`, `test_index_probe.py`, `test_admin_security_cf.py`,
  `test_build_model_load.py` — tổng: **152 passed / 5 skipped** (tăng ratchet so 131).

## Changed
- `itlr/pipelines/build_model.py`: `load_catalog_items()` — chỉ loại hàng khuyết cột cốt
  lõi (có log), ô tùy chọn rỗng giữ "" thay vì NaN (bug âm thầm nổ 5000 hàng).
- `configs/collect.sources.json` — license mô tả trung thực; VNE thêm `link_pattern`.
- `requirements.txt`/`pyproject.toml` — thêm httpx/beautifulsoup4/feedparser; đóng gói
  theo packages.find (itlr*).
- `.env.example` — ITLR_ADMIN_TOKEN + cấu hình crawler.

## Fixed
- `itlr/collect/extract.py`: stale-attrs crash sau decompose (attrs=None guard) và
  trích xuất rỗng cho fCC (container `post-and-sidebar` khớp nhầm "sidebar") — chọn
  main content theo mật độ thay vì chặt rác cấp cao.
- `scripts/collect_data.py`: precedence bug khi ghi `last_run.json` (mkdir sai đường dẫn).
- `itlr/versioning.py`: `_id()` strftime trên struct_time (crash build V2 lần đầu).

## [1.0.0] - 2026-10-27

## Added
- **DeepSeek làm LLM chính**: `itlr/chatbot/llm_client.py` — tầng LLM thống nhất
  (DeepSeek → OpenAI → Ollama), retry/backoff + timeout, token/chi phí tracking,
  `mask_key` chống lộ key, `LLMError` báo rõ (không nuốt lỗi); chatbot chỉ delegate.
- **SYSTEM_PROMPT rule 10** — chống prompt-injection + bắt buộc CITE `[item_id:ID]`
  (context LLM giờ kèm `item_id` từng item).
- **`itlr/pipelines/generate_interactions.py`** — tương tác MÔ PHỎNG latent-persona
  (1.800 users, seed=7, MIN_HISTORY=5, EXPLORATION_CAP=1); backup interactions cũ
  tại `var/data/interactions_backup_500users.csv`.
- **`scripts/build_all.py`** — build artifacts một lệnh, idempotent, có
  `--dry-run/--force/--step`; artifacts ghi vào `var/artifacts` theo `itlr.config`.
- **`eval/eval_generation.py`** — quality generation đo trực tiếp citation
  `[item_id:ID]` (valid/in-context) + hallucination rate; groundedness/relevancy ghi
  rõ là proxy rule-based; `--llm` fail-fast khi chưa có key.
- **`var/data/eval/offtopic_testset.csv`** — 121 câu hand-curated (60 IT / 61 ngoài
  chủ đề) để chốt ngưỡng cổng off-topic bằng dữ liệu.
- **`AGENTS.md` + `docs/PROJECT_MEMORY.md`** — bộ nhớ trong repo về kiến trúc, cấu hình không chứa secret, ADR, build/test/eval và giới hạn.
  Lịch sử có tham chiếu notes #102–#107; giao thức cũ đó đã được thay bằng đọc và cập nhật
  file trong repo. Không tích hợp hoặc yêu cầu Claude-Mem.
- Kết quả eval mới chạy rc=0: `reports/offtopic_eval.md`
  (AUC 0.9825; ngưỡng hiện 0.55 → F1 0.663; tối ưu F1 0.800 → P 0.881 / R 0.983 / F1 0.929)
  và `reports/generation_eval_template.{csv,md,json}`
  (template: groundedness proxy 0.385, relevancy proxy 0.929, refusal off-topic 0/21,
  false-refusal IT 0/29).
- **`tests/`** — 70 test pytest (path-regression, ANN, pickle-handles, llm_client,
  chatbot adapter, generate_interactions, eval generation, scripts/config,
  API-integration khi đã build artifacts).
- Docs: `README.md`, `CONSTRAINTS.md` (sàn quality), `docs/decisions/ADR-001..004`,
  `pyproject.toml`, `requirements.txt`, `Makefile`, `.env.example`.
- `itlr/config.py`: `ITLR_ARTIFACTS_DIR` (override artifacts cho sandbox/test).

## Fixed
- `eval/*.py` — 12 file tính sai ROOT (`dirname × 3` → ×2; `import itlr` hỏng khi
  chạy từ ngoài repo); `eval/run_all.py` path cũ `scripts/eval/…` → `eval/…`.
- `itlr/core/ann.py` — mặc định `artifacts_dir` tương đối (theo CWD) → dùng
  `config.ARTIFACTS_DIR` lazily; `faiss.read_index` giờ fail-safe; file handle
  `pickle.load/dump(open(...))` → `with`-block (ann, engine, build_model,
  build_embeddings, build_cf).
- `itlr/api/server.py` — prewarm Ollama bỏ lại khi cấu hình DeepSeek/OpenAI key.

## Security
- Không log API key; `.env` được loại khỏi repo (chỉ `.env.example`); mask key
  trong mọi chuỗi log/lỗi LLM (`test_exhausted_retries_raise_llmerror_no_key_leak`).

## Changed
- DeepSeek là mặc định generation; `DEEPSEEK_MODEL=deepseek-flash` override qua env.
  Tên model + base_url đã verify với docs chính thức (https://api-docs.deepseek.com/,
  2026-10-27); chưa verify LIVE call vì môi trường không có `DEEPSEEK_API_KEY`.

## 2026-10-29 — Security/runtime remediation (unreleased)

- Static UI renders external values safely; restricts Markdown and URLs; local scripts and CSP.
- Web requires explicit credentials, validates upload signatures and protects pending attachments.
- Constrain proxy trust and single-worker deployment; bound metric path cardinality.
- Verify artifact hashes/path confinement and pin active directory per engine load.
- Add Python/TypeScript/security CI and offline fixture pipeline regression.
- Full production release remains gated; actual results: reports/FINAL_REMEDIATION.md.

## Local models install — 2026-10-29 (in progress)

Installed Torch 2.15.0+cpu, sentence-transformers 6.2.0, FAISS 1.15.1, pyarrow26.
Model caches: var/hf (E5-base), var/ollama/models (qwen2.5:3b). Ollama executable
0.40.13 in var/ollama/bin; full runtime archive is partial, llama-server not yet present.
Downloads encountered github DNS failures and HF timeouts. Do not claim inference PASS.
Fixed resolve_preset(full HF ID) to preserve registered E5 query/passage prefixes;
regression reproduced FAIL then PASS. Full Python suite:201 passed,5 skipped (33.37s),
before usable neural index. Caches/downloads excluded from git. Claude-Mem unavailable.

## Local model verification complete — 2026-10-29

E5-base weights downloaded, real768d embedding smoke PASS; Qwen2.5:3b downloaded,
SHA256 verified and CPU inference PASS through Ollama0.40.13. V2 build/probe/activate
PASS on5,000 synthetic items (version20261029-204546). Real HTTP health/search/chat200;
API Qwen response57.01s with valid retrieved citation2716. Reranker disabled, CF unbuilt.
Direct80-token Qwen smoke omitted citation; no general groundedness/hallucination claim.
Evidence reports/LOCAL_MODELS.md and raw JSON; startup deploy/LOCAL_MODELS.md.
DeepSeek, PostgreSQL/browser and other release gates remain unverified.

## Audit checkpoint — 2026-10-29 (Ponytail ultra)

Confirmed and fixed rolling-feed false missing detection (explicit complete-inventory opt-in),
strict JSON booleans for collection policy, V2 nDCG reuse of standard logarithmic metric,
and small-catalog self-retrieval probe bounds. Regression tests reproduced failures before fixes.
Full suite outside sandbox: 228 passed / 5 existing conditional skips (233 collected).
Web: 59 passed; typecheck/build pass; lint 0 errors / 20 warnings; line coverage 25.01%.
Sandbox FastAPI TestClient hangs in AnyIO portal; outside-sandbox suite passes.
No paid LLM calls, data deletion, activation, migrations or deployment performed.
V3 chunk-vector retrieval and overlapping refresh safety remain unfinished; live DeepSeek,
PostgreSQL, browser, Docker and production load/quality gates remain unverified.
Evidence and scoped audit/review: reports/AUDIT_2026-10-29.md. Claude-Mem unavailable.

## V3 implementation checkpoint — 2026-10-30

Added real chunk-vector FAISS + existing BM25/RRF retrieval to chatbot semantic path,
optional bounded passage CrossEncoder, chunk citation identity validation and persistence of
chunk vectors. Existing V2 item/API search paths remain; no active index rebuild/activation.
Added Linux lifecycle locks, serialized CLI crawl/build and refresh parent jobs, unique staging IDs,
rollback transition tracking, GC staging/rollback preservation, and load-before-swap engine reload.
Temporary versioned API fixtures replace all 5 artifact-conditional skips without deleting assertions.
Final regression:245 Python passed,0 skipped (44.60s);Web59 passed, coverage lines25.01%.
Real E5 experiment:8 source snapshots/98 chunks,8 hand-authored item qrels; both mean-dense and
chunk-hybrid Recall@5/MRR@5/nDCG@5=1.0;p95=117.41/118.36ms. No quality/speed improvement claimed.
Generation faithfulness/hallucination/citation accuracy unmeasured; no paid calls.
Release blockers:V2 API/off-topic paths, real reranker validation, crash-durable pointer/history,
DeepSeek live,PostgreSQL,Docker/browser and full-corpus eval. Claude-Mem tools unavailable.
Evidence:reports/V3_PROGRESS_2026-10-30.md and reports/chunks_v3_experiment.json.

## Shared V3 retrieval and repository migration — 2026-10-30

Baseline245/0 retained;latest full suite256 Python passed/0 skipped (44.63s),Web59 passed.
Web typecheck/build pass;lint0 errors/20 existing warnings;compileall/diff checks pass.
Search,off-topic,semantic chat and quick resources use itlr.retrieval.service for chunk artifacts;
legacy artifact paths remain. V3 generation now requires valid chunk references per cited item.
BM25 implementation moved with git mv to itlr/retrieval/bm25.py; old core module is a pickle/import shim.
CURRENT.json atomically commits pointer+history with fsync; legacy history file remains a mirror.
Process-exit/restart test proves rollback survives pointer/mirror interruption. Corrupt version
reload preserves loaded engine. No runtime data/index activation,paid call or DB migration.
Real E5 experiment8 docs/98 chunks:item mean vs chunk RRF scores all1.0;p95=129.07/130.23ms;
CPU=113.98/114.98ms per query;whole-process peakRSS1468.86MiB. Generation quality unmeasured.
Mapping/review/release limits:reports/V3_RESTRUCTURING_2026-10-30.md and ADR-010.
Docker/psql/postgres absent from PATH;browser/live DeepSeek/real reranker/full-corpus gates pending.
Claude-Mem tools unavailable; fallback memory updated only, no save_memory claim.

Packaging verification: initial namespace discovery stalled at metadata; setting namespaces=false
(regular packages all have __init__.py) allowed offline wheel build to complete. The first wheel
then failed asset inspection: zero static assets. Added explicit itlr.api static HTML/JS/CSS package
data; rebuilt wheel successfully and verified all four UI assets, retrieval modules and legacy
BM25 shim are present. No dependency downloads (--no-index --no-deps --no-build-isolation).

## Streaming continuation - 2026-10-30

- Accept usage-only terminal chunks without reporting a false interrupted stream; fake DeepSeek/OpenAI regression: 2 FAIL to PASS, client suite 34 PASS.
- [Evidence and unresolved gates](reports/HARDENING_STREAM_2026-10-30.md); no retrieval configuration change or production readiness claim.

## Restructuring continuation - 2026-10-30

- Isolate mutable provider usage counters in snapshots (regression FAIL to PASS); remove unused private pointer helper and redundant builder path conversion.
- Update architecture/data-flow documentation and ADR-011 status; preserve historical audit evidence. [Validation](reports/RESTRUCTURING_CONTINUATION_2026-10-30.md).
