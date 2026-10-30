# ITLR–RAG — Final release readiness, 2026-10-30

**Verdict: NO-GO cho production.** Có hai lỗi Web tái hiện được đã sửa; bộ
retrieval mới không tuning đạt Recall@5 83,33%. PostgreSQL staging native chạy
được trong thư mục tạm. Chưa chứng minh generation đáng tin cậy, cancellation
upstream, capacity hoặc deployment Docker/HTTPS production.

## Phạm vi và nguồn bằng chứng

Kế thừa [engineering review](FINAL_ENGINEERING_REVIEW.md) và inventory của nó;
không tính các sửa trước thành sửa mới. Baseline phiên này: **445 Python / 140
Web PASS**, Python statement coverage 66,70%, Web line coverage 46,48%.
HEAD `01703e96dfc9da003480bb3b0ff2d5eacb8382dd`; working tree đã có nhiều thay đổi
chưa commit. Inventory phiên này ghi riêng source hashes, Git status và evidence.

Chỉ dùng `intfloat/multilingual-e5-base` local, 768d, prefixes và normalization
hiện hành; Ollama `qwen2.5:3b` Q4_K_M trên `127.0.0.1:11434`. E5 revision
`d128750597153bb5987e10b1c3493a34e5a4502a`, Qwen digest
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
Corpus staging giữ nguyên **118 snapshots thật / 1576 chunks**. Không cloud
inference, commit/push, production migration hoặc đổi pointer artifacts đang dùng.
Cloud credentials bị unset trong test/runtime processes. Không dừng các dịch vụ
của người dùng tại 8000/4173 hoặc daemon Ollama.

Áp dụng Ponytail, TDD/debugging, security, release validation và fresh-context
adversarial review từ Agent Skills. Một agent soạn bộ đánh giá mới khi chưa xem
rankings; agent khác chạy chẩn đoán/review. Đây không phải panel người dùng hoặc
đánh giá cross-model. Không gọi CLI/cloud để tạo thêm judge.

## Hai bản sửa mới: RED → GREEN

| Lỗi | Root cause, tác động | Sửa và bằng chứng |
|---|---|---|
| Medium: UI báo hoàn tất sai | `web/src/public/app.js:398–433` đặt `completed=true` ngay khi nhận `final`; parser phát hiện thiếu `done` hoặc UTF-8 lỗi sau đó nhưng catch bỏ qua lỗi. Conversation URL có thể đổi khi stream chưa được xác nhận. | Giữ final tạm, chỉ render success và cập nhật conversation sau khi `consume()` resolve. Bốn tests chạy cả `app.js` và parser thật trong VM; RED 3 FAIL/1 PASS → GREEN 4 PASS. Có provisional draft và đường valid final/done. |
| Medium: PDF hợp lệ trả HTTP 500 | `web/src/services/dataset-extract.ts:20` chuyển bytes thành Node Buffer trước khi gọi pdf.js cũ; cùng PDF parse được khi đưa Uint8Array. | Đổi đúng một biểu thức tại worker boundary. Regression dùng PDF có xref hợp lệ và parser/worker thật: RED 1 FAIL/3 PASS → GREEN 4 PASS. Ghostscript PDF qua HTTP: 500 → 200 pending; extracted text và tải BYTEA đúng bytes. |

Không đổi API, schema, ranking, pickle paths, completion contract hoặc dependency
ứng dụng. Worker vẫn giữ time/memory limits và kiểm tra tài liệu không hợp lệ.
Fresh review không tìm thêm lỗi trong completion path đã sửa.

## Retrieval: giải thích chênh lệch, không tuning lại

92,86% raw release, 83,33% holdout và 62,50% confirmation **không phải ba lần đo
cùng một phân phối**. Raw release dùng query gốc tại shared service; hai bộ kia
chạy engine có rewriting và các câu hỏi khác nhau. Release có 21 positive, holdout
12, confirmation 16. Nhãn cũ do engineer soạn, đã được xem trong các vòng debug;
không còn là blind estimates. Với mẫu nhỏ, một query làm thay đổi tỷ lệ đáng kể.

Bộ mới đóng băng trước inference: 12 positive (6 EN/6 VI) trên **12 source IDs
chưa có qrels ở ba bộ cũ**, 8 negatives; SHA256
`2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1`.
Exact quotes đối chiếu snapshot, nguồn khác các IDs đã gán nhãn; không giả định
LLM chưa từng thấy tài liệu công khai trong pretraining. Tất cả tài liệu vẫn nằm
trong index, đúng yêu cầu retrieval; đây không phải train/test document exclusion.
Single fresh AI author, qrels chưa đầy đủ; không chứng minh quality trên người dùng.
Source-ID disjointness không bảo đảm topic/near-duplicate independence; chưa có
semantic overlap audit đầy đủ hoặc hidden human test set.

| Current engine, default84; reranker off như baseline | Kết quả mới |
|---|---:|
| Recall@1 / Recall@5 | 75,00% / **83,33%** |
| MRR@5 / nDCG@5 | 0,79167 / 0,80258 |
| Precision judged@5 | 0,16667; unjudged ≠ irrelevant |
| EN / VI hit@5 | 6/6 / 4/6 |
| Negatives trả rỗng | 8/8; chưa phải exhaustive off-topic guarantee |

Chẩn đoán từng miss, cosine của target sau rewriting:

| Query ID | Target | Cosine | Dense / BM25 rank |
|---|---:|---:|---:|
| noise-venv | 5117 | 0,78123 | 13 / 2 |
| multi-python, target thứ hai | 5121 | 0,83359 | 4 / 1 |
| holdout-vi-5027 | 5027 | 0,82624 | 1 / 1 |
| holdout-vi-5082 | 5082 | 0,83964 | 2 / 1 |
| confirmation-vi-5031 | 5031 | 0,83419 | 1 / 3 |
| confirmation-vi-5062 | 5062 | 0,83898 | 1 / 5 |
| confirmation-vi-5073 | 5073 | 0,82572 | 1 / 20 |
| confirmation-vi-5084 | 5084 | 0,83095 | 1 / 1 |
| confirmation-vi-5098 | 5098 | 0,83519 | 1 / 4 |
| confirmation-vi-5109 | 5109 | 0,81001 | 2 / 17 |
| blind-positive-07 | 5066 | 0,82453 | 1 / 1 |
| blind-positive-11 | 5094 | 0,81831 | 1 / 1 |

Latency bộ mới (20 queries, host dùng chung): p50/p95/p99 **159,68/232,67/239,07ms**.
Không so thời gian này với bộ cũ như một regression/speedup vì tải máy khác nhau.

Mọi target bị hụt đều bị dense floor0,84 loại trước rerank. BM25/RRF thường tìm
đúng target nhưng không thể vượt qua gate. Chạy diagnostic floor0 để nhìn candidates
không phải thay cấu hình phục vụ. BGE reranker local tại floor0,84 không thể khôi
phục các target đã bị loại. Trường hợp multi-python vẫn lấy được 5117, thiếu 5121;
không ghi cả query thành hoàn toàn sai. HMAC bị correction thành `mac`: target
cosine raw 0,84893 → rewritten 0,82572. Đây là lỗi còn lại cần regression trên
development corpus mới; không sửa dựa trên confirmation để nâng điểm bộ đã mở.

Không thay threshold/weights/gate/model. Cần tập development độc lập lớn hơn,
human relevance judgments đầy đủ và một confirmation mới còn kín trước khi xét
thay đổi correction hoặc gating. Không có bằng chứng precision/nDCG được cải thiện
trên population; không suy diễn negatives nhỏ thành an toàn production.

## Local generation và resource limits

Các request thật chạy qua API staging18080 với E5/Qwen và `OLLAMA_TIMEOUT=45`;
đây là budget kiểm thử, khác defaults90s non-stream/240s stream khi không override.
Máy i7-8650U, 4 cores/8 threads, RAM15.221MiB, không GPU, đang có các dịch vụ khác.
Không dùng mock làm bằng chứng inference. Log ghi riêng sources, tokens, final,
done, mode và errors; HTTP200 với refusal/fallback không được tính generation PASS.

Direct Ollama smoke thật trả `OK`, `done=true`, `done_reason=stop` ở cả stream và
non-stream. Wall time **41,57s / 25,97s**, nhưng decode chỉ **0,100s / 0,095s**;
thời gian còn lại gồm scheduling/queue/overhead, không thể gọi là tốc độ decode.
Không có quyền cô lập daemon đang được dùng chung nên chưa quy nguyên nhân queue
cho ứng dụng. Không thay timeout hoặc output limits để làm đẹp kết quả.

Ba blind positives SSE chạm45s, không nhận delta provider, final
`insufficient_evidence/generation_failed`: **45,44 / 45,26 / 45,45s**. Negative ngoài
CNTT đi template0,125s; unsupported IT negative cũng chạm45,27s, nên không tính nó
là successful semantic refusal. Hai non-stream requests đồng thời mất45,56s mỗi
request, HTTP200 nhưng `insufficient_evidence/generation_unavailable`. Context-stress
16 history messages trả fallback45,37s: chưa chứng minh không mất context ở provider.

Client cancellation thật đóng HTTP sau delta đầu ở30,33s; có token từ Qwen nhưng
không có final, đúng thao tác test. Chưa có quan sát/ACK chứng minh Ollama dừng decode
hoặc giải phóng slot sau disconnect. Tách điều này khỏi mock cleanup reproduction.
API shutdown hoàn tất nhưng vẫn ghi **1 loky semaphore warning**; kiểm tra sau đó
không thấy semaphore đó trong `/dev/shm`. Chưa có soak chứng minh leak-free.

RSS samples: API tối đa **1758,34MiB**, llama-server **2307,80MiB**, daemon Ollama
**37,06MiB** trong cửa sổ đo. `ps %CPU` là lifetime average, maxima API13% / runner47%;
không phải CPU tức thời, attribution từng request hoặc utilization của riêng test.
Không cộng các maxima thành peak RAM toàn máy; có user workloads ngoài phép đo.

**Human faithfulness/hallucination: `null`**. Citation identity không xác nhận nội
dung; không có panel độc lập. Cancellation mock chứng minh sync iterator cleanup
phụ thuộc destruction trong Starlette, chưa chứng minh permanent leak ở socket
thật. Blocking read vẫn có thể kéo dài tới socket timeout; elapsed budget chỉ được
kiểm tra ở event boundaries. Context char budget chưa chứng minh chính xác token
budget tiếng Việt cho mọi lịch sử. Không tuyên bố capacity/soak PASS.

## Staging, security và các gate

Docker daemon socket không cho user hiện tại truy cập; không sửa group, global
services hoặc production Compose. PostgreSQL **18.6** từ Ubuntu archive được
download/extract vào `/tmp`, không cài hệ thống; cluster loopback15432, private
socket và credentials0600. Đây không phải bằng chứng tương đương image PG16 trong
Compose. Schema migrations chạy hai lần; chỉ có dữ liệu fixture trong cluster này.

36 checks HTTP Express → PostgreSQL thật PASS: register/login/CITEXT duplicate,
CSRF, progress boundaries, ownership, chat metadata, incomplete SSE không persist,
PDF upload/access/download. Upstream của journey này là fixture HTTP khai báo rõ,
**không phải bằng chứng neural generation**. Xem evidence để phân biệt các lớp.

Bandit: **0 High / 27 Medium / 46 Low**, scanner exit1; 73 findings giống triage
cũ, không gọi clean scan. Các pickle loads chỉ an toàn khi builder/filesystem đáng
tin; hash không xác nhận tác giả nếu thay được cả pickle và manifest. Python image
vẫn chạy root, API volume artifacts RW; chưa chứng minh remote write exploit nhưng
rủi ro hậu quả cao nếu filesystem bị chiếm. Giữ yêu cầu isolation/ACL và kiểm thử
non-root UID/volume ở Docker staging trước release, không sửa UID mù khi thiếu runtime.
Pip-audit: 105 distributions, 0 advisories/0 skipped; npm audit: 0 vulnerabilities.

Native logical backup custom pg_dump → database cô lập thứ hai pg_restore:
**15 bảng cùng row counts/SHA256**, restart cluster giữ dữ liệu. Chrome thật **9
checks PASS**, gồm login sau restart, progress/history persist và ba completion
boundary cases. Browser interception là fixture lỗi có chủ đích, không model output.

Artifact lifecycle trên **temporary root**: copy trusted real E5 artifacts, verify
SHA, pointer a→b, real engine load/reload118 items, rollback vềa, tamper copy bị từ
chối và pointer cũ giữ nguyên: **9 checks PASS**, 19,11s. Không đổi repo active root.
Đây là engine reload trực tiếp, chưa chạy authenticated HTTP reload trong Docker.
Harness đầu dùng env flat-directory override sai với version root; đã sửa harness
để dùng normal pointer resolver, không tính lần lỗi cấu hình harness là bug hệ thống.

TLS transport smoke cũng PASS: temporary certificate có SAN127.0.0.1 được trust
explicit qua verifying SSLContext, **TLS1.3**, GET/login200, CSP/nosniff hiện diện.
HSTS vắng trong NODE_ENV=test; chưa kiểm production secure cookies/public cert/Caddy.
Các dịch vụ fixture15432/18030/18031/18443 và API18080 đã dừng, dữ liệu tạm được giữ.
SMTP/reset mail delivery, moderation approval/catalog export và toàn bộ social/admin
flows chưa được kiểm chứng end-to-end. Không suy diễn các journey đã chạy thành
coverage toàn hệ thống hoặc disaster recovery/PITR trên host khác.

## Quality gates mới chạy

| Gate | Before → current / verdict |
|---|---|
| Python full pytest, không skip | 445 → **445 PASS**, 92,11s |
| Python statement coverage | 3755/5630 = **66,69627%**, không đổi |
| Web full Vitest | 140 → **145 PASS**, 26 files |
| Web line coverage | 634/1364 → **635/1364 =46,55%**; public JS không nằm trong coverage denominator |
| Typecheck / ESLint / build | **PASS** sau sửa PDF |
| Compileall / pip check | **PASS**; không cài app dependencies mới |
| Pip-audit / npm audit | **PASS advisory scan**, 105/0 skipped, 0 vulnerabilities |
| Bandit | **FAIL scanner / conditional triage**, 0H/27M/46L không đổi |
| New frozen retrieval | **MEASURED**, R@5 83,33%; chưa human-validated quality gate |
| Real Qwen smoke stop metadata | **PASS**, cả stream/non-stream |
| Real RAG completion trong budget45s, concurrency2 | **FAIL**, timeout/fallback; host/daemon dùng chung |
| Human faithfulness / hallucination rate | **NOT MEASURED**, `null` |
| Native PG18 migration / HTTP DB / Chrome / restore | **PASS scoped**, upstream fixture ghi rõ |
| Real engine artifact lifecycle | **PASS scoped**, temporary root, không production activation |
| Verified local TLS transport | **PASS scoped**, không production HTTPS/auth cookie proof |
| Docker/PG16/Caddy production parity | **BLOCKED**, daemon socket permission; không sửa hệ thống |
| Upstream cancellation / token-limit guarantees / soak | **NOT VERIFIED**, còn release blocker |

Không chạy `npm ci` để ghi đè node_modules đang dùng chung khi lock không đổi;
checks dùng dependencies đã cài và audit lại. Build/typecheck được chạy, không suy
ra install-from-lock/container reproducibility. Raw logs và scripts trong
[release evidence](release-readiness-evidence/inventory.json).

## Điều kiện mở release

1. Đánh giá human độc lập trên tập mới, gồm tiếng Việt, unsupported questions,
   multi-step và citations; sửa correction/gating chỉ trên development data riêng.
2. Cô lập local model workload; đo TTFT, completion, token accounting, concurrency,
   cancellation upstream và latency/memory dưới tải lặp lại. Giữ từ chối rõ khi lỗi.
3. Chạy đúng Docker/PG16/HTTPS/Caddy deployment với UID/volume permissions, real
   Web→API→Ollama journey, restore rehearsal và soak; không dùng unit PASS thay thế.

Chưa có căn cứ GO. Các bản sửa mới giảm lỗi correctness, không xóa các release gates.

## Chạy local và tái lập

Xem [deployment](../deploy/DEPLOY.md), [local models](../deploy/LOCAL_MODELS.md) và
[staging summary](release-readiness-evidence/POSTGRES_STAGING_SUMMARY.md). Giữ
DATABASE_URL/JWT_SECRET/ADMIN_PASSCODE riêng ngoài Git; không tái sử dụng credentials
fixture. Chỉ chạy migration sau khi xác nhận database cô lập; server startup không
được tự migrate/seed. Không ghi đè dịch vụ đang chiếm cổng.

```bash
# Terminal API, chọn port trống và artifact staging đã build/probe tin cậy.
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:3b \
  OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  HF_HOME="$PWD/var/hf" HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  ITLR_ARTIFACTS_DIR=/tmp/itlr-system-audit/staging \
  ITLR_REQUIRE_ARTIFACT_MANIFEST=1 \
  .venv/bin/python -m uvicorn itlr.api.server:app --host 127.0.0.1 --port 18080 --workers 1

# Terminal Web, với config/DB local riêng đã chuẩn bị theo runbook.
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  PORT=18030 RECOMMENDER_URL=http://127.0.0.1:18080 npm --prefix web start
```

Đường dẫn `/tmp` là fixture của phiên này, không phải deployment artifact được
phân phối. Scripts evidence ghi nguyên đường dẫn/revisions để tái lập trên máy
hiện tại; cần dựng lại staging từ snapshot khi chuyển máy. Không copy private env,
TLS key, database dump hoặc Chrome profile vào reports. Inventory chỉ thu evidence
đã chọn, source hashes và trạng thái Git; không chứa operational credentials.
