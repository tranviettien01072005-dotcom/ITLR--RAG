# RAG quality và production release validation — 2026-10-30

**Verdict: NO-GO.** Baseline đầu checkpoint: 410 Python PASS/0 skip, 132 Web PASS;
coverage 65,71% statements / 45,31% lines. Giữ nguyên working tree, API/schema,
pickle paths, V2/V3, model và ranking weights. Không commit/push, gọi API trả phí,
cài Docker/WSL, tạo cloud hoặc thay database/artifacts runtime.

## 1. Kết quả retrieval trên snapshot thật

Đã thêm `eval/release_queries.jsonl` và `eval/eval_release_retrieval.py`, tái sử dụng
builder/search/metrics hiện có. Dataset gồm **118 tài liệu thật**, **23 truy vấn**:
8 English, 8 tiếng Việt, 3 nhiễu, 2 nhiều bước và 2 không có đáp án. Hai câu nhiều
bước cần hai tài liệu. Qrels có quote evidence được kiểm tra trực tiếp trong snapshot;
được đóng băng trước khi xem ranking. Một bản nháp dùng từ append cho snapshot Python
bị cắt trước phần đó đã bị evidence guard từ chối trước khi benchmark; truy vấn cuối
chỉ hỏi indexing/slicing có trong snapshot.

Nhãn là **engineer-authored**, chưa exhaustive và chưa có người đánh giá độc lập.
Tám truy vấn English kế thừa qrels cũ; không gọi toàn bộ tập này là independent human
evaluation. Hash corpus và queries được lưu trong [raw result](release-retrieval.json).

So sánh hai cấu hình lexical hiện có trên cùng corpus/query/config: TF-IDF + BM25,
MMR tắt/bật, `top_n=10`, đọc metrics tại K=1/5/10; 5 lượt/query/variant, tổng 230
request đo. Thứ tự variant luân phiên theo lượt. Build time không nằm trong query
latency; throughput là serial requests/s, không phải tải concurrent của service.

| Chỉ tiêu | Lexical baseline | Lexical + MMR |
|---|---:|---:|
| Recall@5 | 1,0000 | 0,9762 |
| MRR@5 | 0,8690 | 0,8730 |
| nDCG@5 | 0,9035 | 0,8943 |
| Precision@5 theo judged items | 0,2190 | 0,2095 |
| Latency p50 / p95 / p99, ms | 54,68 / 67,20 / 71,40 | 56,51 / 70,56 / 74,50 |
| Serial throughput, requests/s | 18,81 | 18,09 |
| Empty-result rate trên 2 câu không đáp án | 0,0 | 0,0 |

**Whole-process peak RSS: 275,39 MiB**, đo bằng Windows ProcessMemoryInfo, gồm build
và cả hai cấu hình; chưa đo RAM riêng từng variant. Precision chỉ tính item đã gán
nhãn: đa số câu chỉ có một gold item, nên không diễn giải 0,2190 là tỷ lệ đúng theo
human labels đầy đủ. Các item chưa gán nhãn có thể vẫn liên quan.

Recall@5 baseline là 1,0 ở từng nhóm positive; MMR là 1,0 ở English/Việt/nhiễu và
0,75 ở hai câu nhiều bước. Không dùng kết quả nhỏ này để đổi ranking production:
MMR giảm Recall/nDCG@5 và chậm hơn nhẹ, dù MRR nhích lên. Cả hai trả tài nguyên cho
câu thiếu đáp án; đây là retrieval diagnostic, **không phải refusal accuracy**.

Reproduce từ repo root, chọn output path mới khi cần bảo toàn lần đo trước:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY \
  USE_OLLAMA=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
  .venv/bin/python eval/eval_release_retrieval.py \
  --cases eval/release_queries.jsonl --repeats 5 --out reports/release-retrieval.json
```

Windows dùng `.venv/Scripts/python.exe`, `PYTHONUTF8=1` và `PYTHONIOENCODING=utf-8`.

## 2. Audit V3: điều đã xác minh và phần bị chặn

| Thành phần | Quan sát code thực tế | Quyết định |
|---|---|---|
| API/Web search | `min_pct=90` đi thành raw dense cosine 0,90 | Giữ nguyên; chưa có calibration neural mới |
| Chat off-topic | Default 0,80, override có validation; V3 lấy max dense chunk | Không suy rộng kết quả lexical sang gate này |
| FAISS | IndexFlatIP, vectors/query normalized; tìm trên toàn chunk rows | Exact search; memory/latency neural scaling chưa đo |
| BM25 + RRF | Filter cosine/type trước candidate truncation, RRF k=60 | BM25 không cứu được chunk đã bị dense floor loại |
| Unique items | Chọn item khác nhau khi yêu cầu; chat giữ passage evidence | Không đổi candidate/Top-K |
| CrossEncoder | Chấm lại candidate pool có giới hạn, kiểm score length/finite | Không có cache model để chạy real reranker |

`min_pct=90` là hard floor, không phải xác suất câu trả lời đúng. Nguy cơ mất recall
khi lexical match tốt nhưng cosine dưới floor là hệ quả của code, **chưa phải số đo
loss trên E5** trong checkpoint này. Không thay threshold dựa trên TF-IDF experiment.

Không có model cache hoặc active index đủ điều kiện trên máy hiện tại. Neural V3,
chunking alternatives, reranker, FAISS scaling và threshold sweep: **BLOCKED / NOT
MEASURED**. Benchmark lexical ở trên không mô phỏng embedding bằng vector giả để
gắn nhãn thành neural quality.

## 3. Generation và streaming reliability

Faithfulness, citation support, answer relevancy, hallucination và refusal accuracy:
**null / NOT MEASURED**. Không có provider/model local sẵn sàng hoặc human labels độc
lập; không gọi API trả phí. Citation identity tests xác minh contract, không đo semantic
entailment. Before/After generation quality vì vậy đều NOT MEASURED.

Giữ tương thích legacy cho OpenAI-compatible stream thiếu finish metadata, nhưng thêm
WARNING **completion unverified** ở clean EOF không có stop metadata. Regression đã
FAIL trước sửa và PASS sau sửa; explicit non-stop reason/transport failure vẫn fail.
Clean EOF bị cắt mà không có metadata không phân biệt được chắc chắn với legacy EOF;
warning không biến tình huống đó thành generation đã được chứng minh hoàn tất.
Không thêm strict-mode config hoặc đổi public iterator/API.

Full regressions của DeepSeek/OpenAI/Ollama, partial/retry/cancellation, Web SSE và
auth/admin/upload/lifecycle đã chạy trong suite. Fake SDK/fixtures không thay live
provider, browser E2E hay PostgreSQL integration trên staging.

## 4. Production staging và recovery

| Gate | Kết quả |
|---|---|
| Dockerfile/Compose/Caddy/config templates | Đã đối chiếu code/static; chưa build image |
| Docker/Podman, PostgreSQL CLI, Mermaid renderer | Không có trên PATH; staging không được cung cấp |
| Migration/catalog sync/authenticated SSE/browser E2E | BLOCKED, không chạy với DB thật |
| Backup/restore/activation/rollback/recovery trên staging | BLOCKED; tests chỉ dùng temporary fixtures |
| HTTPS và loaded-version proof | NOT VERIFIED; `/health` chưa có loaded-version fingerprint |

Đã bổ sung [isolated staging acceptance drill](../deploy/PRODUCTION.md#isolated-staging-acceptance-drill-not-executed):
dedicated workspace/var/secrets và Compose project; build/migrate/sync/health; actual
login/chat/cancellation/ownership cases; restore vào database mới fail-if-exists;
artifact activation/rollback/corruption/restart drill. Không tự chạy các thao tác này.

Compose project riêng **không** tự cô lập bind-mounted var. API còn chạy root và mount
var writable; least privilege, artifact ACL và permissions cần chứng minh trên target.
Subnet/proxy trust IP của template cũng cố định; cùng-host staging cần network override
được review hoặc dùng host Linux riêng. [Static staging checks](release-staging-static.json)
ghi riêng các điều đúng và hai kiểm tra non-root/read-only chưa đạt; không coi YAML parse
là Docker build hoặc runtime PASS.
Đã sửa mô tả sai rằng `/health` cung cấp provenance: endpoint hiện chỉ trả readiness,
items, CF. CURRENT.json là disk state, không chứng minh engine đã reload đúng version.
Loaded-version observability là khoảng trống nghiệm thu, không được ghi PASS.

## 5. Quality và security gates thực chạy

| Gate | Baseline | Kết quả mới |
|---|---|---|
| Python | 410 PASS/0 skip | **414 PASS/0 skip**, 86,51s |
| Python coverage | 65,71% | **65,73%** (3683/5603 statements) |
| Web | 132 PASS | **132 PASS**, 25 files |
| Web line coverage | 45,31% | **45,31%** |
| Typecheck / ESLint / build | PASS | PASS |
| Compileall / pip check | PASS | PASS |
| Bandit itlr/scripts | 27 Medium / 47 Low, 0 High | Cùng số finding; exit 1 vì còn findings |
| Bandit evaluator mới | Chưa có | 0 findings, exit 0 |
| pip-audit online | Kết quả cũ không tái sử dụng | 88 distributions, 0 advisories, exit 0 |
| npm audit online | Kết quả cũ không tái sử dụng | 0 vulnerabilities, exit 0 |

Log/result: release-python.log, release-python-coverage.json, release-web.log,
release-focused.log, release-stream-red.log, release-bandit.json,
release-eval-bandit.json, release-pip-audit.json, release-npm-audit.json.
Một pytest cache permission warning còn tồn tại; không thêm skip hoặc giảm assertions.
Final focused regression/evaluation/CLI/Markdown gate: **75 PASS**, log
release-final-checks.log. [Document check](release-doc-check.json): 54 Markdown paths/
anchors PASS, gồm report release mới; corpus/query hashes khớp kết quả benchmark.

74 Bandit findings đã được đối chiếu theo [triage](final-bandit-triage.json): 22 Medium
pickle-load là executable-input risk, chỉ chấp nhận trusted builder/ACL; 5 Medium
URLopen dùng URL operator-controlled, cần scheme/network isolation. Low gồm RNG
synthetic/eval, import-only, subprocess argv và tolerant diagnostics/extraction.
Đây là rủi ro chấp nhận có điều kiện, không phải false assertion “scanner sạch”.
Không thêm suppression và không thay pickle compatibility để làm giảm số finding.

## 6. Điều kiện để xem xét GO

1. Chạy isolated Linux staging drill đầy đủ; lưu image digests, version/hash đang phục
   vụ, HTTPS/authenticated E2E, rejection paths và sanitized evidence.
2. Chứng minh backup/restore và rollback/restart trên dữ liệu staging; không chỉ kiểm
   file backup tồn tại. Xác nhận ownership/progress/chat và tài liệu phân biệt version.
3. Đánh giá V3 neural với distractors, CrossEncoder on/off và threshold calibration
   trên frozen qrels được người đánh giá độc lập review; chốt quality targets trước
   khi tuning, báo theo tiếng Việt/nhiễu/multistep/unanswerable và uncertainty.
4. Đánh giá generation trực tiếp bằng source-supported human labels: faithfulness,
   citation support, relevancy, hallucination và refusal; tách proxy khỏi direct metrics.
5. Nghiệm thu least privilege, artifact trust/ACL, các accepted Medium risks, monitoring
   và loaded-version evidence. Không coi warning legacy EOF là completion verified.

Chưa điều kiện nào ở trên được thay thế bởi benchmark lexical nhỏ. **NO-GO**.
