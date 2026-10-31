# Production blockers resolution — ITLR–RAG, 2026-10-30 → 2026-10-31

**Verdict: NO-GO.** Đã sửa nguyên nhân cancellation/transport có regression thực.
Timeout45s của prompt uncached và citation passage không hỗ trợ claim vẫn là
blocker; không tăng timeout hoặc giảm chất lượng để ghi PASS. Docker production và
human validation chưa đủ điều kiện kiểm chứng.

## Baseline, quyền và phạm vi

Kế thừa [release readiness](RELEASE_READINESS_FINAL.md) và SHA256 inventory:
**445 Python / 145 Web PASS**, coverage66,70% Python statements /46,55% Web lines.
Git bắt đầu sạch tại `6fcc1cd1f3db61a36f0a72f13ecc7159148173bb`, nhánh main.
Không commit/push trong phiên này. Không lặp audit các journey DB/TLS đã PASS;
chỉ tái dùng fixture DB để kiểm chứng cancellation xuyên các tầng.

E5 `intfloat/multilingual-e5-base`768d, revision
`d128750597153bb5987e10b1c3493a34e5a4502a`; Qwen2.5:3b Q4_K_M digest
`357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b`.
Chỉ local SentenceTransformers/Ollama, cloud credentials unset. Corpus staging
118 snapshots thật/1576 chunks giữ nguyên, không activation hoặc sửa embedding.
Không production schema/migration, không đổi threshold/ranking/model hoặc dependencies.
Các dịch vụ người dùng8000/4173/11434 được giữ. Linux i7-8650U4cores/8threads,
RAM15.221MiB, CPU-only; model daemon/host dùng chung.

Skills áp dụng: Ponytail, systematic debugging, TDD, performance profiling,
security và code review. Agent viết regression trước khi sửa và review độc lập;
agent profiling chạy DEV experiments riêng. Nhãn AI không được tính human ground truth.

## Root causes và bản sửa

| Finding | Bằng chứng RED | Sửa nhỏ nhất và GREEN |
|---|---|---|
| P0: API disconnect không đóng provider kịp thời | TCP provider thật đứng trước delta làm API chờ readtimeout3s; sau delta socket còn mở khi giữ response object. Hai tests FAIL10,57s. | API SSE dùng async engine/adapter/httpx transport; `aclosing` xuyên các tầng; ASGI response đóng generator khi send thất bại, cleanup shielded. Giữ sync public methods cho V2/V3 callers. Cancellation tests yêu cầu<1s và provider EOF/RST trong0,5s. |
| Lỗi phát hiện trong triển khai async: UTF-8 bị thay thế âm thầm | `httpx.aiter_lines()` chấp nhận FF hoặc E2 82 chưa đủ bytes trong JSON text; RED2FAIL/1PASS. | Strict incremental UTF-8 decoder trên `aiter_bytes()`, vẫn hỗ trợ fragmentation byte-by-byte. Không xuất corrupt content như delta hợp lệ. |
| Deadline chỉ được kiểm tra tại event boundaries | Transport cũ không thể kiểm tra elapsed deadline trong lúc đọc blocking; disconnect phụ thuộc threadpool/destruction. | `asyncio.timeout()` bao quanh async Ollama generation và HTTP context managers; cancellation không bị `except Exception` chuyển thành success. Provider lookup/retrieval ở ngoài generation deadline, không gọi45s là toàn bộ request SLO. |

Regression7 tests gồm hai cancellation cases, timeout sau draft chỉ tạo một failed
final/done, UTF-8 lỗi2cases/fragment hợp lệ và ASGI2.4 send OSError khi generator
đang suspended. Timeout/partial-final contract trước đó vốn PASS, không tính là
bug mới đã sửa. Năm async SDK tests dùng fake local bảo toàn retry-before-delta,
cleanup, history và legacy completion warning; không gọi cloud API.

Files hành vi: `itlr/api/server.py`, `itlr/api/streaming.py`, `itlr/engine.py`,
`itlr/chatbot/{chatbot,llm_adapter,llm_client}.py`. Retrieval/prompt construction
dùng chung; chỉ thêm transport async cần thiết, không tạo service hierarchy mới.
`tests/test_grounded_citations.py` giữ assertions cũ, chuyển sang đọc async response
thật; thêm `tests/test_stream_cancellation.py` và `tests/test_llm_async.py`.

Giới hạn: retrieval worker thread không thể bị cưỡng bức dừng CPU; cancellation
ngăn generation bắt đầu sau khi await bị hủy. Custom legacy engine chỉ có sync
iterator vẫn có giới hạn threadpool; RecommenderEngine hiện tại cho cả V2/V3 dùng
async path. Cloud compatibility được unit-test, không có inference/network cloud.

## Cancellation xuyên Browser → Express → FastAPI → Ollama

Chrome thật đăng nhập fixture PostgreSQL có sẵn; không migrate/seed lại. Express
trỏ API mới, API dùng E5 staging thật và Qwen thật. Observation proxy chỉ forward
HTTP tới Ollama11434, lưu hash/timing và socket state; không thay model response.
Không intercept response trình duyệt trong hai cases thành công này.

| Real Stop case | Đóng socket Ollama sau Stop | UI sẵn sàng | Qwen OK probe tiếp theo |
|---|---:|---:|---:|
| Trước delta đầu,0draft chars |0,06384s|0,03070s|0,32710s,done/stop|
| Sau delta đầu,4draft chars |0,07716s|0,02096s|0,31078s,done/stop|

Cả hai xóa draft, giữ URL/conversation và không lưu user/assistant partial: DB
counts3/3 của user fixture trước/sau không đổi. Đây là bằng chứng real upstream socket cancellation
và nhận request tiếp theo, không chỉ AbortSignal/mock. Backend command có np1 nhưng
không có per-request internal cancellation ACK từ Ollama; không tuyên bố mọi prefill
batch/decode đã dừng tức thời hoặc queue toàn cục luôn rỗng. Shared runner CPU trong
1s windows sau Stop vẫn218,5%/202,9%; một cửa sổ5s sau các phép đo cuối về0%, nhưng
đó vẫn là quan sát toàn process, không attribution chính xác cho request đã hủy.

Hai lỗi harness Chrome ban đầu (scroll/DOM node navigation race) được giữ riêng,
không tính là lỗi application hoặc Stop PASS. Sau kiểm chứng, ports15432/18030/
18080/18435 đã đóng, fixture DB giữ nguyên. Shutdown API vẫn có1loky semaphore
warning như checkpoint cũ; chưa chứng minh leak-free bằng soak.

## LLM profiling: tách implementation, cache và hardware

Tất cả RAG requests dùng output limit2000, temperature0,3, budget45s; không nới để
đạt completion. E5 load13,061s, DEV retrieval/preparation72,7–108,3ms. Không unload
shared model để giả lập cold start: **model cold start NOT MEASURED**.

| Request thật, trực tiếp Ollama | Prompt chars | Total / TTFT(s) | Kết quả |
|---|---:|---:|---|
| Warm minimal OK |14|0,349 /0,224|stop,2tokens,15,90decode tokens/s|
| DEV404 warm |5811|6,671 /0,228|stop,42tokens,6,52tokens/s|
| DEV5061 full prompt |6015|45,046 /null|timeout, không delta|
| Concurrent2: DEV404 |5811|15,206 /8,453|stop,42tokens,6,22tokens/s|
| Concurrent2: DEV5061 |6015|22,623 /15,352|stop,44tokens,6,06tokens/s|

4RAG calls/2DEV queries: observed provider completion3/4=75%; descriptive elapsed
p50/p95 kể cả request timeout18,915/41,683s. Successful-only TTFT p50/p958,453/14,662s.
Timeout là quan sát censored tại45s; p95 mẫu nhỏ không phải uncensored population
latency/SLO. Các lần hoàn tất là gần như toàn bộ prompt-cache hits:1420/1419 hoặc
1386/1385 prompt/cached tokens. Không suy diễn uncached prompt cũng đạt45s.

Đã tái hiện failure **không qua Express/FastAPI**, định vị bottleneck tại provider
prefill/scheduling/hardware. Smoke41,57s trong checkpoint trước nay0,35s, nên không
thể gán ổn định cho parser hay decode. Concurrent successful metadata còn khoảng8s
unattributed: phù hợp queue overhead nhưng chưa có per-request scheduler telemetry.
Runner command có context4096, `-np1`, batch512/context-shift; không sửa daemon args.

Interval CPU sampling từ `/proc`, khoảng250ms: runner mean367,88%, p95427,06%,
max514,80% (100%=một logical CPU), peak RSS2445,74MiB. E5 process RSS1742,78MiB,
daemon35,76MiB. Shared runner có thể xử lý workloads khác; không cộng các maxima
thành whole-host peak hoặc gán toàn bộ CPU cho riêng request. Các successful prompts
tối đa1420tokens và output42–44, dưới loaded context4096; chưa tái hiện overflow ở
mẫu history-free. Boundary/history/token accounting production **NOT VERIFIED**.

### Context optimization có đo nhưng không đưa vào runtime

Chỉ dùng DEV5061; giữ source IDs/titles/URLs, exact evidence windows có các method
cần trả lời và injection guard. Nonce diagnostic prefix làm cache reuse quan sát
được; đây không phải prompt production nguyên trạng.

| Condition | Prompt | Total /TTFT | Quality |
|---|---|---|---|
| Full5sources, nonce |6073chars|45,003 /44,876s|partial `Context`, timeout, không stop|
| Exact windows, same5IDs |2743chars,762tokens/cached9|29,842 /22,488s|stop54tokens,7,35decode tokens/s; thiếu method, item citation và trích sai passage|

Prefill của bản rút gọn22,258s cho762tokens, khoảng34,24tokens/s: giải thích áp lực
budget từ prompt trước decode. Không chứng minh đây là bottleneck duy nhất. Bản
rút gọn **bị loại**, không giảm context/output hoặc đổi prompt phục vụ để lấy PASS.
Không có bằng chứng quality-preserving prompt optimization đủ mạnh để triển khai.

## Retrieval và faithfulness

Không tuning confirmation/holdout hoặc nhãn AI. Kế thừa nguyên phép đo frozen mới
Recall@5 **83,33%**, EN6/6, VI4/6; chưa chạy lại ranking vì không sửa retrieval.
Hai miss là configparser5066 và argparse5094: target dense/BM25/ungated RRF đều
rank1, cosine0,82453/0,81831 bị floor0,84 loại. Reranking candidates đã qua gate
không thể khôi phục target. RRF weights, default84 và off-topic gate không đổi.
Chi tiết từng query, dataset SHA và giới hạn source overlap ở release report.

Một counterexample thực: answer DEV5061 nói `__enter__`/`__exit__`, ID citation hợp
lệ nhưng dẫn5061:7; excerpt đó nói closing/aclosing, không chứa các method này.
Các chunks5061:0/14/1 có methods. Đây là **observed unsupported-passage citation**,
không tự gọi toàn bộ câu trả lời sai hoặc ước lượng hallucination rate của người dùng.
Exact answer/excerpts/provenance lưu ở `citation-support-spotcheck.json`.

Human faithfulness/groundedness/hallucination/answer relevance **null / NOT VERIFIED**.
Packet cho human review giữ query, output, exact supplied evidence và fields null;
không coi AI-authored expected claims là đáp án human. Cần reviewers độc lập và
adjudication trước khi mở gate này. Citation membership đơn thuần không đủ.

### Fresh frozen generation evaluation, không tuning

Giữ nguyên SHA256 dataset `2a3a98e2d207b7c4932ced6ec87b3d7db9668c8b543730545e9a76d10abe6dd1`.
Chạy current async engine tuần tự với2 positives và1 unsupported IT negative;
không sửa prompt/model/ranking sau khi xem kết quả.

| Frozen ID | Total /TTFT(s) | Raw completion và final contract |
|---|---:|---|
| blind-positive-01 |14,018 /2,056|Model trả câu trả lời nhưng không citation; final insufficient_evidence|
| blind-positive-08 |28,225 /20,158|Có chunk citation, thiếu item citation; final insufficient_evidence|
| blind-negative-08 |17,499 /3,169|Draft nói không có nguồn Cisco/BGP; không citation; final insufficient_evidence|

Provider stream về bình thường qua completion validation3/3 trong budget45s (suy
ra từ async stream return; engine không expose terminal token counters); không
phải application accepted completion: **hai positive accepted grounded answers0/2**.
Không tính expected negative refusal là positive answer failure hoặc suy ra human
refusal accuracy1/1. Cả3final có `generation_error=citation_validation_failed`, giữ
strict guard; không tự chèn citations để biến câu chưa kiểm chứng thành PASS.
Descriptive elapsed p50/p95 của3cases17,499/27,153s, TTFT3,169/18,459s; N nhỏ và cache
khác các phép đo DEV, không dùng làm Before/After speedup. Raw draft/citation status
và final đều có evidence; `human-review-packet.jsonl` chứa outputs/evidence/fields
null, protocol không cung cấp AI labels như human answers.

## Docker production staging

**BLOCKED**, không ghi PASS từ native PostgreSQL/TLS của checkpoint trước.
`docker info` exit1: socket root:docker0660 từ chối user1000. Rootlesskit preflight
thật thất bại vì thiếu `newuidmap`; `newgidmap`, slirp4netns/fuse-overlayfs cũng vắng.
Noninteractive `sudo -n docker version` cũng bị từ chối vì cần xác thực tương tác;
Docker chỉ có context mặc định trỏ socket này. Không cài global packages, đổi
group/socket ACL hoặc khởi động daemon hệ thống.

Do đó Compose/Caddy/PG16 image permissions, TLS production cookies, restart/rollback
trong Docker chưa được kiểm chứng. Native PG18 migration2runs/HTTP36/Chrome9/backup
restore15tables/TLS smoke của release trước vẫn là scoped evidence, không tương
đương production Compose. Python image root + RW artifact volume vẫn là conditional
risk cũ; trusted filesystem/builder là điều kiện để unpickle an toàn.

## Final regression và security scans

| Gate | Before → After mới chạy |
|---|---|
| Full Python pytest |445 → **457 PASS/0skip**,72,30s|
| Python statements coverage |3755/5630=66,70% → **3871/5757=67,24%**|
| Full Web Vitest |**145 PASS**,26files, không đổi Web source|
| Web line coverage |**635/1364=46,55%**, không đổi|
| Typecheck /ESLint /build |**PASS**|
| compileall /pip check |**PASS**|
| Bandit |**0High/27Medium/46Low**, scanner exit1; retained conditional triage, không clean-scan PASS|
| pip-audit |105distributions,0skipped,0advisories|
| npm audit |0vulnerabilities|

Không bỏ assertions, không skip/xfail, không nới threshold hoặc thay dependency.
Full regression bao gồm các V2/V3/pickle/API/SSE cases cũ; public sync interfaces
và PostgreSQL schema giữ nguyên. Security findings không tăng; SHA256 không thay
thế trusted builder/ACL cho pickle. Không chạy npm ci đè node_modules đang được
user service dùng khi lock/dependencies không đổi; install/container parity vẫn
là gate riêng. Source review và real runtime evidence tách khỏi mock SDK tests.

## Gate verdict và hướng xử lý còn lại

| Gate | Verdict |
|---|---|
| Local transport cancellation + strict completion/UTF-8 | **PASS scoped**, regression và real Browser-to-Ollama; internal compute ACK chưa quan sát |
| Uncached generation hoàn tất trong45s | FAIL, tái hiện trực tiếp tại Ollama |
| Quality-preserving context optimization | NOT ACCEPTED, thử nghiệm rút gọn giảm chất lượng |
| Supported citations/human quality | FAIL counterexample / human NOT VERIFIED |
| Frozen retrieval policy | UNCHANGED, inherited83,33%; không suy diễn production accuracy |
| Docker/PG16/Caddy production | BLOCKED theo host preflight |
| Cold model, context boundaries, capacity/soak | NOT VERIFIED |

Cần môi trường Docker staging có quyền hợp lệ và isolated local model workload để
đo cold/warm/queue/cancellation capacity. Phải xử lý/đánh giá passage-support trên
development data có nhãn human và giữ confirmation mới kín; không tăng timeout
hoặc thay model trái phạm vi để hợp thức hóa các request đang fail.

## Evidence và tái lập

[Inventory](production-blockers-evidence/inventory.json) ghi source/evidence SHA256,
Git status và model/corpus provenance. Raw scripts/logs/results, independent review,
failed harness logs và human packet nằm cùng thư mục; không copy private credentials,
DB data/dumps, TLS keys hoặc Chrome profile. Historical reports giữ nguyên.

Để kiểm tra regression sau sửa, dùng lệnh của AGENTS với cloud keys unset. Local
runbook [LOCAL_MODELS](../deploy/LOCAL_MODELS.md) giữ Qwen/E5; API SSE hiện dùng async
transport với total generation deadline, còn sync public stream giữ event-boundary
budget cũ. Chọn port trống, DB/artifact staging riêng; không tự restart các dịch vụ
người dùng, không activation hoặc production migration để tái lập benchmark.
