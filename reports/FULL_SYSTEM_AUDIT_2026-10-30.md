# Full-system audit và remediation — Linux local, 2026-10-30

**Verdict: NO-GO cho production.** Các bản sửa có bằng chứng chạy mới; không chứng
nhận toàn repository hết lỗi. PostgreSQL, Docker/HTTPS staging, backup/restore,
capacity dài hạn và đánh giá generation độc lập chưa được xác minh.

## Phạm vi, inventory và quyền thực thi

- Bắt đầu tại HEAD `01703e9`, working tree sạch, Linux x86_64 kernel 7.0.0-42.
  Python/venv 3.14.4; Node 22.22.1; npm 9.2.0. CPU i7-8650U, 4 cores/8 threads,
  RAM 15.221 MiB, swap 4.095 MiB. Không có `nvidia-smi`; Ollama báo 100% CPU/0 VRAM.
- Ollama 0.40.13; Chrome 156.0.8078.79. `qwen2.5:3b` Q4_K_M, 3.1B, digest
  `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`;
  API `/api/ps` báo loaded size 2.168.360.795 bytes, context 4096. Đây không phải
  phép đo peak RSS toàn service hoặc capacity nhiều người dùng.
- E5 cache đã có ở `var/hf`; inference SentenceTransformers 6.2.0/Torch 2.15.0
  offline thành công. Query `(768,)`, passage `(1,768)`, norm 0,99999994/1,0;
  giữ `query: ` / `passage: ` và L2 normalization. Cached revision
  `d128750597153bb5987e10b1c3493a34e5a4502a`. Không tải/chọn model thay thế.
- Docker client 29.9.2 có sẵn nhưng daemon socket permission denied kể cả ngoài
  sandbox. PostgreSQL binaries/service không có; không mở cổng 5432. Không sửa
  group/quyền hệ thống để vượt ranh giới này.
- `var/artifacts` không tồn tại lúc inventory. Staging và SQLite thử nghiệm chỉ ở
  `/tmp/itlr-system-audit`; không tạo CURRENT.json của application, không activation,
  migration/seed DB người dùng, GC runtime, commit/push hoặc paid/cloud LLM calls.
- Cài Web theo lockfile bằng `npm ci --ignore-scripts`; không đổi lockfile.
  Coverage/Bandit/pip-audit ở venv tạm `/tmp/itlr-audit-tools`, không nâng packages
  ứng dụng. Python coverage dùng interpreter ứng dụng, thêm đường dẫn tooling sau
  các site-packages ứng dụng. Cloud credentials bị unset trong tiến trình kiểm tra.

Đã đọc AGENTS, CONSTRAINTS, README, memory, kiến trúc/ADR-010, deployment,
restructuring/stream/release reports và Git diff. Không lấy số Windows cũ làm kết
quả Linux mới. Skills áp dụng: Ponytail, agent-skills TDD/debugging/security/code
review/git workflow, browser testing và verification-before-completion.

## Findings và RED → GREEN

| Severity | Root cause / vị trí | Tác động | Bằng chứng và sửa |
|---|---|---|---|
| P1 | `itlr/chatbot/llm_client.py`, `ollama_chat` chỉ đọc content | Response error/`done=false`/EOF hoặc `done_reason=length` có thể thành câu trả lời thành công | 4 invalid-response cases thực sự FAIL trước sửa; validate object, `done is True`, finish reason và message/content type; HTTP context đóng trên cả lỗi. 6 invalid cases PASS sau sửa; hai ca schema trước đó đã raise qua wrapper nên không tính là RED mới. Qwen thật `max_tokens=1` bị từ chối cả chat/stream. |
| P1 | `ollama_model` dùng installed list thay explicit model thiếu | Không tái lập được cấu hình; chạy model khác dù operator chỉ định | 1 FAIL → PASS; explicit `OLLAMA_MODEL` trả nguyên tên, Ollama báo thiếu model thay vì substitution. Hành vi auto-select khi không đặt vẫn giữ để tương thích. |
| P2 | `chat`/`stream` chỉ trim history trong cloud branch | Ollama bỏ `char_budget`, tăng context/latency và nguy cơ mất lượt mới | 2 FAIL → PASS; dùng helper có sẵn trước provider branch, giữ system/latest, input không bị mutate. Character budget vẫn là xấp xỉ, không phải tokenizer-exact cap. |
| P2 | `timeout_for` bỏ tham số provider | `OLLAMA_TIMEOUT=240` trong runbook/smoke không có hiệu lực | 7 FAIL → PASS: 2 chế độ + 5 invalid values; honor explicit local timeout, kiểm finite/positive, giữ legacy defaults khi biến chưa đặt. |
| P2 | `web/vitest.config.ts` không cấp env cho test import real config | Checkout sạch thiếu `.env` khiến 4 suite collection FAIL, chỉ 110 tests chạy | Credentials fixture ở Vitest, DB loopback port 1; không thay validation runtime. Sau sửa 25 files/132 tests PASS, auth config tests vẫn fail-closed. |
| P2 | `web/src/views/home.ejs` và `partials/auth-aside.ejs` hardcode 50.000 | Giao diện quảng cáo quy mô không có căn cứ dữ liệu | Assertion FAIL và screenshot browser trước sửa; bỏ con số, assertion PASS và DOM Chrome sau sửa không còn claim. Không thay bằng con số snapshot/staging như quy mô runtime. |
| P1 | `itlr/versioning.py:63`, `write_manifest` chốt inventory trước khi engine tạo `.activation.lock` trong flat artifact root | Real staging probe đầu tiên FAIL integrity dù toàn bộ data files đúng | 1 regression FAIL → PASS; tạo lock bằng exclusive-create trước hash, không truncate file đã có, giữ mọi SHA256/symlink checks. 34 focused lifecycle/integrity/probe tests PASS; fresh clone chưa có lock/manifest probe PASS ngay lần đầu. |

Regression LLM đầu: **7 FAIL / 2 PASS**; sau nhóm đầu **62 PASS**. Timeout group:
**7 FAIL**, sau sửa toàn LLM client **69 PASS**. Không xóa assertion, skip/xfail,
đổi model/index compatibility hay giảm quality gate. Review diff sau từng nhóm;
không đổi REST/SSE schema, PostgreSQL schema, V2/V3 layout hoặc BM25 pickle shim.

Vị trí các sửa khác: `llm_client.py:119` timeout, `:152` model, `:167` non-stream,
shared trimming trong `chat`/`stream`; `web/vitest.config.ts:7`; EJS home `:5`,
auth aside `:7`. Manifest mới giữ lock trong inventory. Flat manifests cũ bị lỗi
này cần operator re-probe trusted staging; không bỏ hash check hoặc viết lại active manifest.

## Quality gates chạy mới

| Gate | Before trong phiên | Final / phạm vi |
|---|---|---|
| Python full pytest | 414 PASS, 0 skip, 62,64 s | **431 PASS, 0 skip, 75,26 s** |
| Python statement coverage | NOT MEASURED trước sửa trong Linux phiên này | **3713/5615 = 66,13%**, toàn `itlr/`; số 65,73% Windows là lịch sử |
| Web full Vitest | 4 suite FAIL vì thiếu env, 110 tests PASS | **25 files, 132 PASS**, lines **614/1355 = 45,31%** |
| TypeScript / ESLint / build | Chạy trước sửa Vitest đều PASS | **PASS** sau thay đổi config/templates |
| compileall / pip check | pip check PASS | **PASS**; không broken requirements |
| pip-audit application venv | Không dùng kết quả lịch sử | **105 distributions, 0 advisories, 0 skipped**, JSON có Torch/FastAPI/SentenceTransformers đúng venv |
| npm audit committed lockfile | Không dùng kết quả lịch sử | **0 vulnerabilities**, không `audit fix --force` |
| Bandit `itlr scripts` | Không dùng số lịch sử làm scan mới | **FAIL scanner exit 1: 0 High / 27 Medium / 47 Low**, không suppression |
| SQLite import snapshot | Chưa chạy | **PASS**: import hai lần, 118 docs/118 stable IDs |
| Real artifact build/probe | First probe FAIL integrity do lock sinh muộn | **PASS** sau fix, kể cả fresh flat directory; 118 items/1576 chunks/768d, FAISS, self-retrieval 30/30 |
| E5 offline inference | Chưa chạy | **PASS**, model/prefix/768d/L2 assertions |
| Qwen generation thật | Chưa chạy | Transport PASS; semantic quality chưa đạt acceptance độc lập |
| Real API staging | Chưa chạy | HTTP/validation/auth/CF/reload/SSE protocol **PASS**; end-to-end generation **FAIL usefulness**: non-stream thiếu citation; stream incomplete sau 533,73 s |
| Browser public forms | Chưa chạy | **PASS**: login/register 390/1280px, không overflow, 0 page/console error |
| Web HTTP boundaries | Chưa chạy live | **PASS**: `/health` 200, `/ready` 503 khi DB unavailable, anonymous API 401, POST thiếu CSRF 403, nosniff |
| PostgreSQL integration / authenticated browser journeys | Không có PostgreSQL | **BLOCKED**, không coi mocks là DB integration |
| Docker/Compose/Caddy/HTTPS / backup restore | Daemon permission denied | **BLOCKED** runtime; chỉ review config/source |
| CrossEncoder thật / load soak / memory leak / independent labels | Không có setup/nhãn tương ứng | **NOT MEASURED** |

Vite cảnh báo config CommonJS đang dùng ESM syntax; không ảnh hưởng exit code,
không đổi module system chỉ để tắt cảnh báo. Sandbox không cho tạo socket khiến
TestClient treo; đã hủy run đó, chạy baseline/full suite ngoài sandbox theo AGENTS.
Npm install đầu trong sandbox lỗi DNS; rerun ngoài sandbox mới thành công. Các lần
browser harness chọn nhầm extension target hoặc đọc DOM trước navigation đã được
sửa trong harness tạm; chúng không được trình bày như lỗi của application.

## Kiến trúc, data flow và security đã kiểm tra

Web routes → middleware/auth/CSRF → services/parameterized PostgreSQL → HTTP adapter
→ FastAPI → engine → shared V3 retrieval hoặc legacy V2 → chatbot evidence/citation
→ shared LLM client. Offline: configured sources/robots/rate-limit → extraction/
normalization/SQLite → catalog → builders → staging/probe → explicit activation.
Kiểm thử hiện có chạy các boundary ingestion, chunk/FAISS/BM25/RRF, history, SSE
UTF-8/malformed/terminal/cancellation, admin auth, integrity và lifecycle fixtures.
Các kiểm thử này dùng cả fakes; không suy ra live crawler/cloud/production đã chạy.

Snapshot import kiểm allowlist, license và SHA256 text trước khi ghi SQLite tạm;
chạy hai lần giữ stable IDs. Không crawl website ngoài configured scope. Crawler
source kiểm public HTTP(S), tất cả DNS addresses, redirects, robots, status/retry,
timeout và per-request throttle; DNS rebinding TOCTOU vẫn cần egress policy.
Bandit Medium là trusted pickle load và operator-configured URLopen; triage lịch
sử ở `final-bandit-triage.json` vẫn chỉ là chấp nhận có điều kiện ACL/egress,
không phải đã loại bỏ rủi ro. Không bật `nosec` hoặc bỏ scanner findings.

Dockerfiles/Compose giữ single worker, external runtime artifacts/cache, readiness,
networks/volumes và Caddy proxy contracts. Chưa build/run Docker nên chưa chứng minh
image reproducibility, signal handling trong container, TLS hoặc volume permissions.
Existing Linux temporary-fixture lifecycle tests PASS không thay restore drill.

## Retrieval trên snapshot thật

Corpus: **118** checked-in snapshots, `data/curated_resources.jsonl`; **23** frozen
queries ở `eval/release_queries.jsonl`: English/Vietnamese/typo/multistep/irrelevant/
unanswerable. Judgments engineer-authored, item-level, chưa exhaustive và không phải
panel người dùng độc lập. Precision chỉ trên items đã được judged; item chưa gán
nhãn có thể liên quan. Không thay scoring/threshold từ fixtures hoặc số đo này.

Lexical benchmark `eval/eval_release_retrieval.py --repeats 5`, 115 calls/variant:

| Variant | Recall@5 | Precision judged@5 | MRR@5 | nDCG@5 | p50/p95/p99 ms |
|---|---:|---:|---:|---:|---|
| Lexical | 1,0000 | 0,2190 | 0,8690 | 0,9035 | 65,26 / 73,66 / 79,33 |
| Lexical + MMR | 0,9762 | 0,2095 | 0,8730 | 0,8943 | 68,17 / 76,22 / 80,34 |

Cả hai trả kết quả cho hai câu negative: empty-result rate 0,0; đây là retrieval
diagnostic, không phải refusal accuracy. Latency CPU local, không phải SLO dưới tải.
Neural staging dùng cả 118 documents/**1576 chunks**, E5-base 768d + FAISS flat IP +
BM25/RRF, không CrossEncoder. Build encode mất **953,6 s** với OMP/MKL=2. Probe
validate rows/dimensions/finite/norm/unique IDs, self-retrieval **30/30**, engine
subprocess thành công. Không activate version. Hai cấu hình chạy 23 queries × 2,
encode query nằm trong latency; đây là shared retrieval raw-query, không có query
rewrite của HTTP search. Không bật MMR trong đường chunk V3 này.

| Variant | Recall@5 | Precision judged@5 | MRR@5 | nDCG@5 | Recall@10 | p50/p95/p99 ms |
|---|---:|---:|---:|---:|---:|---|
| Default cosine floor 0,90 | 0,0476 | 0,0095 | 0,0476 | 0,0476 | 0,0476 | 83,36 / 101,60 / 102,98 |
| Diagnostic floor 0,00 | 0,5238 | 0,1143 | 0,4762 | 0,4628 | 1,0000 | 80,66 / 97,22 / 106,73 |

Ở K=10, diagnostic precision judged 0,1095, MRR 0,5361, nDCG 0,6227. Default trả
rỗng cả hai negatives, diagnostic trả kết quả cho cả hai. **Quality concern P1 còn
mở:** default floor làm mất phần lớn positives trên bộ frozen labels này. Không
tự đổi floor sang 0 hoặc gọi diagnostic là fix: sẽ đánh đổi negative rejection,
và 21 positive item judgments chưa đủ calibration độc lập. Không suy ra corpus
khác/human labels sẽ có cùng điểm. Hai negative queries không đủ đo false-positive
rate production. Cần calibration/acceptance dataset độc lập trước khi thay defaults.

Peak process RSS của probe parent + engine/benchmark **1760,02 MiB**, không gồm
Ollama runner hoặc API subprocess. Raw results ghi corpus/query SHA256 và từng query,
K=1/5/10; không có thay đổi nhãn, thuật toán hoặc threshold ứng dụng.

## Generation local thật và giới hạn chất lượng

Ollama `qwen2.5:3b`, `http://127.0.0.1:11434`, cloud credentials unset.
Hai frozen queries English/Vietnamese dùng oracle evidence quote thật của item
5001, mỗi query chạy chat và stream, temperature 0, max output 192 tokens.
Đây là provider/evidence smoke, **không phải end-to-end RAG evaluation**.

| Case | Chat seconds | Stream seconds | Quan sát |
|---|---:|---:|---|
| English Docker/root | 19,31 | 5,23 | Cả hai có `[item_id:5001]`; stream thêm diễn giải Rootless không thể dùng citation identity để chứng minh đúng |
| Vietnamese cùng evidence | 4,28 | 3,78 | Cả hai từ chối trả lời, không citation; chưa đạt kỳ vọng usefulness |
| Truncation `max_tokens=1` | 1,52 | 0,14 | Cả hai raise LLMError đúng contract |
| Unanswerable giá vàng ngoài nguồn | 2,45 | — | Quan sát “Insufficient evidence.”, chỉ một mẫu |
| Cancellation | — | 0,73 tới delta đầu | Đóng generator sau delta đầu thành công |

Python client peak RSS 32,22 MiB, **không bao gồm Ollama runner**. Không lấy mẫu nhỏ
làm tỷ lệ hallucination/refusal: `faithfulness`, `hallucination_rate`, independent
human evaluation giữ **null**. Hai câu dùng cùng quote không đủ để đổi prompt/model
hoặc calibration của toàn hệ thống. API integration real staging có kết quả riêng bên dưới.

### API staging end-to-end: transport PASS, generation chưa đạt

Chạy Uvicorn loopback 18080 với strict manifest và artifacts staging riêng; không
dùng fixture encoder hoặc fake provider. `/health` 200 báo **118 items, ready,
CF=false**. Search min_pct=70 trả 200; query quá dài 422; personas/for-you 503 vì
không build CF; thiếu admin token 403, token tạm đúng reload 200. Không activate
pointer hoặc build interactions synthetic để làm CF có vẻ sẵn sàng. Health không
có loaded-version fingerprint; provenance dựa thêm vào staging path/hash/probe,
không xem health/CURRENT đơn lẻ là chứng minh loaded version.

Cùng frozen English Docker/root query với history rỗng:

- Non-stream **61,15 s**, HTTP 200 nhưng final `generation_mode=insufficient_evidence`,
  `generation_error=citation_validation_failed`, citation status `missing`.
- SSE **533,73 s**, **2004 events**, có sources/meta/text, đúng một final rồi done.
  Provider phát đủ token budget rồi báo incomplete; final `insufficient_evidence`,
  `generation_error=generation_failed`. Citation ID/chunk validation có thể valid
  trong provisional text, nhưng không biến completion bị cắt thành thành công.
- Ollama read timeout 240 s là timeout chờ I/O, **không phải total wall-clock
  deadline**; token tiếp tục đến nên stream có thể kéo dài hơn. Không thêm deadline
  hoặc đổi output budget/prompt chỉ từ một sample; cần acceptance về latency/output
  trên đúng CPU/model. Đây là performance/quality limitation còn mở, không phải PASS
  generation vì HTTP 200 hoặc vì có citation.

API shutdown đóng listening socket và exit. Log còn cảnh báo Python resource_tracker
về **1 loky semaphore** sau shutdown; chưa chứng minh memory/resource leak dài hạn,
chưa tìm được root cause thuộc application. Không suppress warning hoặc coi cleanup
hoàn toàn PASS. Dependency versions và raw log được giữ để điều tra tiếp; capacity,
soak và total generation deadline vẫn chưa được xác lập.

Isolation probes sau đó load E5 hai lần và load/reload engine trong worker thread,
clear cache/exit bình thường đều hoàn tất, không tái hiện semaphore warning. Vì vậy
không quy lỗi cho model cache/reload rồi thêm cleanup phỏng đoán. API/Web ports
18080/18030 và baseline pytest sandbox bị treo đã được dừng; Ollama daemon/cache
của người dùng được giữ nguyên.

## Chạy lại và vận hành local

Lệnh unit/template theo AGENTS vẫn dùng `USE_OLLAMA=0`; đó là isolation, không
thay cấu hình inference thật. Thực thi từ repo root:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY USE_OLLAMA=0 DISABLE_RERANKER=1 \
  OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python -m pytest tests/ -o addopts='' -q -ra
.venv/bin/python -m compileall -q itlr scripts eval
.venv/bin/python -m pip check
cd web
npm ci --ignore-scripts
npm run typecheck
npm run lint
npm run build
npm test
npm audit
```

Inference local cần artifacts build/probe riêng, không tự activate staging audit:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  ITLR_ARTIFACTS_DIR=/tmp/itlr-system-audit/staging \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:3b OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  OLLAMA_TIMEOUT=240 DISABLE_RERANKER=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 \
  OPENBLAS_NUM_THREADS=1 ITLR_REQUIRE_ARTIFACT_MANIFEST=1 \
  .venv/bin/python -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 8000 \
  --workers 1 --no-proxy-headers
```

Đường `/tmp` là artifact audit tạm, không có trong Git và có thể mất sau reboot.
Máy khác cần build/probe staging từ snapshot; không chạy builder mặc định vào active
root để tái lập. Web local cần PostgreSQL/credentials riêng theo README. Chỉ chạy
migration/seed sau khi operator xác định database cô lập; phiên này không chạy.
Tài liệu chính thức đã đối chiếu: [Ollama chat response](https://docs.ollama.com/api/chat)
và [E5 model card](https://huggingface.co/intfloat/multilingual-e5-base).

## Điều kiện còn thiếu để GO

1. PostgreSQL tạm thật: register/login/ownership/history/progress/upload và
   authenticated browser SSE; migration/schema/seed acceptance trong DB cô lập.
2. Docker/HTTPS staging có quyền daemon: build/run, network/volume ACL, shutdown,
   artifact activation/rollback, backup/restore và recovery drill.
3. Independent Vietnamese/English passage labels và generation evaluation;
   kiểm faithfulness/usefulness ngoài citation membership, CrossEncoder thật.
4. CPU/RAM capacity, sustained load, cancellation tới provider, file handles và
   leak/soak trên thời gian đủ dài. Character budget và local limiter chưa chứng
   minh token-exact limit hoặc multi-host safety.

Không kết luận production-ready từ full suite xanh hoặc inference smoke. Không có
quyền activation/publish trong yêu cầu này; không xin quyền để tự chuyển verdict.

## Bằng chứng lưu trong repository

[Evidence directory](full-system-audit-evidence-2026-10-30) giữ logs/JSON chạy mới:

Inventory sửa: `llm_client.py`, `versioning.py`; hai regression test files;
Vitest config và hai EJS templates; README, changelog, local-model runbook, memory,
validation và báo cáo/evidence này. Mọi thay đổi còn uncommitted, không có user diff
đầu phiên bị ghi đè. Các harness `generation.py`, `runtime.py`, `browser.py`,
`coverage_run.py` trong evidence là bản đã chạy, có assertions; giữ nguyên workspace
và `/tmp` paths của phép thử. Chúng là hồ sơ tái lập, không phải CLI portable hoặc
quy trình tự deploy. `runtime.py` cần staging đã build; coverage harness cần tooling
venv tạm. Browser harness chỉ kiểm public pages bằng dedicated profile, không đăng
nhập profile thật hoặc ghi database. Không dùng chúng với DB production.

- [Python final](full-system-audit-evidence-2026-10-30/final-python.log),
  [coverage](full-system-audit-evidence-2026-10-30/python-coverage.json),
  [Web final](full-system-audit-evidence-2026-10-30/web-green.log).
- [Ollama RED](full-system-audit-evidence-2026-10-30/ollama-red.log),
  [timeout RED](full-system-audit-evidence-2026-10-30/timeout-red.log),
  [manifest RED](full-system-audit-evidence-2026-10-30/manifest-red.log),
  [fresh probe GREEN](full-system-audit-evidence-2026-10-30/probe-fresh.json).
- [Neural benchmark](full-system-audit-evidence-2026-10-30/retrieval-neural.json),
  [lexical benchmark](full-system-audit-evidence-2026-10-30/retrieval-lexical.json),
  [real generation](full-system-audit-evidence-2026-10-30/generation.json),
  [browser checks](full-system-audit-evidence-2026-10-30/browser.json).
- [API outcomes](full-system-audit-evidence-2026-10-30/api.json),
  [API log, gồm completion error và shutdown warning](full-system-audit-evidence-2026-10-30/api.log).
- [Bandit](full-system-audit-evidence-2026-10-30/bandit.json),
  [pip audit](full-system-audit-evidence-2026-10-30/pip-audit.json),
  [npm audit](full-system-audit-evidence-2026-10-30/npm-audit.json).

Screenshot/DOM có cookie CSRF không được đưa vào repository; structured browser
checks chỉ giữ viewport/status/console outcome. Source data, runtime cache/models,
SQLite và pickle/FAISS staging giữ ngoài Git. Không lưu admin token tạm vào report.
