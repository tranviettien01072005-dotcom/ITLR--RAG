> **Ngữ cảnh đồ án — 2026-10-30:** Tài liệu lịch sử: giữ số đo, phạm vi và kế hoạch tại thời điểm ghi. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](README.md).

# Báo cáo nghiên cứu chi tiết repo `ITLR RAG`

> Ngày: 2026-10-27 · 46 file Python (~6.750 dòng KLOC) + 2 file JSON tri thức + 1 web UI tĩnh + 2 CSV dữ liệu.
> Repo **không có** `.git`, không README, không requirements/pyproject, không unit test.

---

## 1. Đây là hệ thống gì?

**ITLR = IT Learning Recommender** — hệ gợi ý + chatbot giáo dục cho người học CNTT, tiếng Việt,
xây trên nền Retrieval-Augmented Generation (RAG). Người dùng tìm/thảo luận về khóa học & tài liệu CNTT;
hệ trả lời 3 năng lực:

1. **Tìm kiếm ngữ nghĩa** hybrid 2 tầng trên catalog 5.000+ tài nguyên (lên tới 50.000 khi build đầy đủ).
2. **Chatbot giáo dục** — cổng off-topic, hiểu viết tắt/sửa chính tả, trả lời khái niệm, lộ trình nghề,
   so sánh, thống kê… có **LLM (OpenAI/Ollama)** hoặc fallback **template không cần LLM**.
3. **Gợi ý cá nhân hóa** — Collaborative Filtering item-basedertoire ("Dành cho bạn", 40 persona).

Kèm theo là **khung đánh giá khoa học** rất đầy đủ (ablation, kiểm định thống kê, beyond-accuracy,
off-policy, LTR, human-label, latency) và **pipelines build artifacts** từ dữ liệu synthetic.

Chất lượng code cao: comment tiếng Việt giải thích rõ *vì sao*, mọi module fail-safe.

---

## 2. Cấu trúc thư mục

```
ITLR RAG/
├── itlr/                     # package chính (thư viện engine + chatbot + eval + pipelines)
│   ├── config.py             # đường dẫn tập trung (ROOT/var/...), env override
│   ├── engine.py             # RecommenderEngine: nạp artifacts 1 lần, API Python thuần
│   ├── core/                 # lớp thuật toán
│   │   ├── recommender.py    # (922 dòng) primitive retrieval/scoring/hybrid/RRF/MMR/CF…
│   │   ├── pipeline.py       # phễu multi-stage ranking + ablation_configs
│   │   ├── rag.py            # EducationalRAG (TF-IDF/BM25 + RRF + fused rerank)
│   │   ├── bm25.py           # BM25 Okapi thuần Python
│   │   ├── ann.py            # FAISS/hnswlib ANN, fail-safe → brute-force
│   │   ├── rerank.py         # Cross-Encoder (BAAI/bge-reranker-base)
│   │   └── embeddings.py     # registry model E5/BGE-M3/MiniLM + query/passage prefix
│   ├── chatbot/
│   │   ├── chatbot.py        # (1.616 dòng) EducationalChatbot — pipeline chính
│   │   ├── intent_router.py  # định tuyến intent regex tiếng Việt
│   │   ├── knowledge_base.py # tri thức offline: 360 concepts, 19 nghề, đồ thị skill
│   │   ├── query_understanding.py  # sửa typo/mở rộng viết tắt
│   │   ├── data/it_glossary.json   # 360 khái niệm CNTT (định nghĩa, alias, đúng chủ đề)
│   │   ├── data/it_roles.json      # 19 vai trò IT (roadmap, lương, phỏng vấn) + 13 gợi ý chọn nghề
│   │   └── opencode_client.py      # wrapper CLI `opencode` (HIỆN KHÔNG được dùng — dead code)
│   ├── eval/                 # khung metric: metrics/diversity/significance/cf_eval/off_policy/ltr_features/loader
│   ├── pipelines/            # build_model → build_embeddings (→ANN) → generate_interactions → build_cf
│   ├── data/                 # generate_items (catalog synthetic), generate_interactions (latent-factor)
│   └── utils/                # runtime_patches (silence warning), repickle (mày mò pickle sau refactor)
├── eval/                     # script chạy thực nghiệm (đáng lẽ nằm dưới scripts/eval/ — xem §7)
│   ├── make_judgments.py     # sinh qrels tự động + bộ test cho người gán nhãn
│   ├── run_evaluation.py     # ablation 7 cấu hình × qrels, chế độ --noisy, viết reports/*
│   ├── eval_cf.py, eval_off_policy.py, eval_offtopic.py, build_ltr.py,
│   ├── bench_latency.py, evaluate_human.py, prepare_labeling_sheet.py,
│   ├── adapt_real_data.py    # adapter dataset Kaggle thật → schema, khử trùng lặp
│   └── run_all.py            # orchestrator chạy toàn bộ bằng 1 lệnh
├── var/
│   └── data/                 # it_learning_items.csv (5.000 items), interactions.csv (12.342 dòng, 500 users)
├── (chưa tồn tại) var/artifacts/, reports/, var/data/eval/   # output build/eval
└── itlr/api/static/index.html + orbital-timeline.{css,js}     # Web UI tĩnh (search/chat/for-you)
```

---

## 3. Kiến trúc runtime

### 3.1 Tầng nạp (engine.py)

`load_engine()` (@lru_cache, nạp 1 lần/process) đọc từ `var/artifacts/`:

- `item_list.pkl` — DataFrame catalog (item_id, title, type, level, description, category, topics, instructor, platform, link)
- `retrieval_model.pkl` — 3 vectorizer+matrix TF-IDF (full/title/topics), BM25Index, categories, topic_index
- `embeddings.pkl`, `search_meta.pkl` — vector E5 item + tên model + prefix
- `char_vectorizer.pkl`, `char_matrix.pkl` — TF-IDF char n-gram **đã bỏ dấu** (chịu lỗi chính tả/thiếu dấu)
- `cf_model.pkl` — ma trận item_sim sparse top-50, popularity, phần lịch sử 40 persona demo
- Rồi dựng: SentenceTransformer + ANN (FAISS/hnswlib — *lưu ý bug đường dẫn, §7*) + CrossEncoder + `EducationalChatbot`

`RecommenderEngine` expose `search()`, `chat()`, `chat_stream()`, `personas()`, `for_you()`.

### 3.2 Phễu xếp hạng 4 tầng (core/pipeline.py + recommender.py)

Chính thức hóa cấu trúc mà hệ vốn ngầm có, cho phép bật/tắt từng tầng (ablation):

| Tầng | Chức năng | Kỹ thuật |
|---|---|---|
| **0. Candidate gen** | 5.000 → ~600 | max(embedding ANN, char n-gram bỏ dấu); hoặc TF-IDF/BM25/hybrid lexical; hoặc **RAG-Fusion** (truy vấn gốc + bản bỏ dấu, hợp nhất RRF) |
| **1. L1 rank** | hybrid rẻ | trọng số chỉnh tay: tfidf 0.42 · bm25 0.18 · category 0.14 · topic_jaccard 0.12 · topic_contain 0.06 · title_overlap 0.05 · type 0.03 |
| **2. L2 rerank** | top-48 | Cross-Encoder bge-reranker-base, hoặc LightGBM LambdaMART (LTR) |
| **3. Re-order** | đa dạng | MMR λ=0.7 + luật category liên quan (`RELATED_CATEGORIES`, bonus 0.55/0.35/0.15) |

Cổng hiển thị sản phẩm: `ABS_RELEVANCE_GATE=0.48`, `ABS_ITEM_FLOOR=0.42`, điểm % hiển thị được
**calibrate** về dải 90–100% qua `calibrate_confidence` (t^0.7 — đường cong lõm, item đầu bảng
rõ ràng hơn; không đổi thứ tự).

### 3.3 Chatbot (chatbot.py, 1.616 dòng — trung tâm sản phẩm)

`_prepare()` chạy pipeline trước khi sinh câu trả lời:

1. **Hiểu truy vấn** (`query_understanding.py`): sửa lỗi gõ (bảng COMMON_TYPOS + difflib cut-off 0.84
   chỉ áp token ≥4 ký tự), mở rộng viết tắt (ml/k8s/db…; `ai`/`be`/`ui` chỉ mở rộng khi token đơn),
   phát dòng "🔎 Mình hiểu ý bạn là…" lên đầu.
2. **Xử lý tiếp nối cụt** (`_resolve_followup`): câu ≤8 từ thiếu thực thể → nối 2 lượt user gần nhất.
3. **Định tuyến intent** (`intent_router.py`, regex trên văn bản đã bỏ dấu): 10 intent — definition,
   comparison, career_path, skill_gap, next_skill, time_estimate, admin_stat, interview, salary,
   career_guidance; `_route_multi` tách câu đa ý theo mệnh đề (`?`, `;`, "và") route từng ý (mượn
   khái niệm mệnh đề trước cho clause cụt chủ ngữ).
4. **Cổng off-topic TẬP TRUNG** chạy sớm: `query_relevance_max` (max điểm khớp catalog qua kênh
   semantic/char) < **0.55** → thông điệp từ chối lịch sự; *trừ* câu đã khớp alias khái niệm an toàn
   (token ≥3 ký tự hoặc đủ viết tắt hoa) — tránh chặn oan "Học AI thế nào?".
5. **Handler intent** khi có giá trị cao; có LLM thì handler output biến thành `kb_block` (dữ liệu
   kiểm chứng) tiêm vào system prompt, yêu cầu LLM viết lại giữ nguyên số liệu.
6. **Truy hồi ngữ nghĩa** `multi_query_search`: biến thể truy vấn (gốc/enriched lịch sử/expanded)
   → RRF → cross-encoder 1 lần trên top-32 → MMR; cổng off-topic mức query riêng `gate_query` tránh
   lặp từ của biến thể expanded thổi phồng điểm char. Fallback: `EducationalRAG.build_context`
   (TF-IDF multifield + BM25 + topic-index boost + RRF + fused rerank). Sau truy hồi,
   `dominant_category()` (chuyên mục đa số top-5) là chuyên mục "đúng" — tin hơn đoán từ từ khóa.
7. **Gợi ý kèm** `get_recommendations` (item↔item từ cosine TF-IDF + hybrid_v2, pool 300).
8. **Sinh câu trả lời**:
   - **mode LLM** (OpenAI `gpt-4o-mini` nếu có key, else **Ollama qwen2.5:3b** auto-phát hiện model đã
     pull; streaming SSE; pre-warm lúc startup): system prompt 9 quy tắc đầy đủ (chỉ trích từ catalog
     khi gợi ý, định nghĩa 1 lần đầu, đa ý trả đủ…).
   - **mode template** `synthesize_answer` (khi LLM không khả dụng, hoặc mode `search` thuần):
     5 dạng — *learning_path* (chấm `difficulty_rank` 3 giai đoạn 3-4-3, **backfill** từ catalog đúng
     cấp độ + đa dạng chủ đề), *compare*, *search*, *recommend*, *answer*; kèm "Tài nguyên tham khảo"
     và khối follow-up gợi ý câu hỏi tiếp.

Tri thức nội bộ (`knowledge_base.py` + JSON): 360 CONCEPTS (định nghĩa/alias/mức/VD/related),
19 CAREERS (roadmap milestone kỹ năng + lương VN 2024–25 + câu hỏi phỏng vấn), đồ thị NEXT_SKILL,
6 cặp so sánh có "phán xét" (Java vs Python…), hàm ước lượng thời gian học.

### 3.4 API FastAPI (api/server.py) + UI tĩnh

- Endpoints: `GET /health`, `GET /metrics` (Prometheus-like text), `POST /api/search`,
  `POST /api/chat`, `POST /api/chat/stream` (SSE — giải quyết timeout 30s proxy vì model local
  chậm 30–135s/câu), `GET /api/personas`, `POST /api/for-you`, `GET /api/suggested`, `POST /admin/reload`,
  UI tại `/`. Static: `index.html` (2 tab chính + chat streaming), CSS/JS `orbital-timeline` —
  tức là UI phiên bản mới đang được làm.
- `lifespan` nạp engine sớm + **pre-warm Ollama** (thread nền) để tránh cold-start ~90s ở câu đầu.
- Nếu thiếu artifacts → báo hướng dẫn build (vẫn boot được, chỉ /health 503).

### 3.5 CF (pipelines/build_cf.py + recommender.recommend_for_user)

- Item-based co-occurrence: `R.T@R` chuẩn hóa `√(pop_i·pop_j)` (cosine), giữ **top-50** láng giềng/item
  (sparse — tránh ma trận dày 50k×50k).
- Feed "Dành cho bạn" = tổng sim tới lịch sử user; lịch sử rỗng → **popularity** (cold-start);
  điểm hiển thị calibrate "90–100% phù hợp với bạn"; nối thêm các item user vừa bấm "Quan tâm".

---

## 4. Dữ liệu

| Tệp | Nội dung |
|---|---|
| `var/data/it_learning_items.csv` | **5.000** mục: 2493 khóa học / 2507 tài liệu, 26 chuyên mục, 3 cấp độ (Cơ bản 2001 / Trung cấp 1850 / Nâng cao 1149); schema 10 cột |
| `var/data/interactions.csv` | **12.342** tương tác của **500 user** (không timestamp) |

Cả hai đều là **dữ liệu synthetic** (mặc định sinh 50.000 — snapshot dùng 5.000):

- `data/generate_items.py`: taxonomy 26 chuyên mục × 3 level × topics thực tế (Python, Docker, K8s…),
  template tiêu đề/mô tả theo level, **có chủ đích mô phỏng lỗi dịch máy** (cụm từ lặp) —
  code có `clean_display_text` gộp lặp tại tầng hiển thị.
- `data/generate_interactions.py` (nâng cấp 2026-06-23): **latent-factor model** — mỗi item có vector
  `q_i` dựng từ category+topics; mỗi user quanh 1 trong 40 archetype; P(tương tác) ∝ exp(p_u·q_i),
  kèm bias phổ biến Pareto. Điểm mấu chốt: phiên bản cũ lấy mẫu theo popularity thuần → co-occurrence
  không có tín hiệu cộng tác → CF eval không-rò-rỉ ≈ 0. Phiên bản mới bảo đảm "người học X cũng học Y"
  XUẤT HIỆN THẬT — comment ghi rõ chuyện này.

---

## 5. Khung đánh giá (nghiêm túc nhất trong repo — phần vàng của `itlr/eval/` + `eval/`)

### 5.1 Metric & thống kê (`itlr/eval/`)

- `metrics.py`: P@k, R@k, HitRate@k, NDCG@k (gain 2^rel−1, chiết khấu log2), MAP, MRR — graded (0/1/2), macro-average.
- `diversity.py`: Catalog Coverage, ILD (1−cosine trung bình cặp), Novelty (−log2 p), Serendipity, Gini.
- `significance.py`: paired bootstrap 10k (CI95 + p hai phía), paired t-test (scipy fallback z), **Cohen's Kappa**.
- `cf_eval.py`: Leave-one-out (CF vs popularity baseline), Temporal split **có** và **KHÓ có rò rỉ**
  (bản clean train lại item_sim chỉ từ phần train của mọi user — held-out không tham gia co-occurrence).
  Ghi chú trung thực: interactions không timestamp → thứ tự dòng làm proxy thời gian.
- `off_policy.py`: IPS / SNIPS / Doubly Robust với propensity logging/target, bootstrap CI, **ESS
  (effective sample size)**, naive on-policy để đối chiếu lệch.
- `ltr_features.py`: 15 đặc trưng per (query,item): tfidf, bm25, emb_cos, char_cos, **cross_enc**,
  category_match, jaccard, containment, title_overlap, type_is_course, n_topics, desc_len, popularity,
  level_rank, title_len.

### 5.2 Thực nghiệm (`eval/`)

- `make_judgments.py`: qrefs tự động theo luật topic-match (grade 2 = cùng category, 1 = khác category —
  *sinh từ metadata, KHÔNG từ điểm hệ thống* → không vòng tròn); chế độ **--natural**: truy vấn câu tự
  nhiên từ glossary, **mask token tiếng Anh** để chống rò rỉ lexical; sinh bộ human-judgments
  (lấy mẫu phân tầng + negative) và phiếu gán nhãn **mù với auto_grade**.
- `run_evaluation.py`: chạy 7 cấu hình ablation (`P.ablation_configs`: TF-IDF only → BM25 → hybrid
  lexical → E5 → +L1 → +Cross-Encoder → +RAG-Fusion+MMR) trên qrels; chế độ **--noisy** perturb
  truy vấn (bỏ dấu + hoán/xóa ký tự 4–6%, nhãn giữ nguyên) → đo độ bền; xuất reports/results.csv,
  per_query.csv, **tables.md** (bảng ablation + kiểm định Full vs từng baseline + beyond-accuracy).
- `eval_cf.py`, `eval_off_policy.py` (mô phỏng bandit có ground-truth để **CHỨNG MINH tính không thiên
  lệch** của estimator — CI phải phủ giá trị thật), `eval_offtopic.py` (biến lựa chọn ngưỡng cổng
  0.55 "cảm tính" thành quyết định dựa trên AUC ROC/P-R/F1 trên bộ test IT vs ngoài lĩnh vực).
- `build_ltr.py`: LightGBM **LambdaMART**, hard-negative mining (70% near-miss từ candidate gen +
  30% random), SHAP importance + reliability diagram, so LTR-vs-heuristic trên test held-out (sạch +
  noisy) có kiểm định, tự lập luận trung thực trong báo cáo (trên nhãn topic-match, heuristic chỉnh
  tay chạm trần NDCG≈1.0; LTR đóng góp phương pháp luận — học từ dữ liệu + giải thích được).
- `bench_latency.py`: p50/p95/p99/QPS của từng tầng; so FAISS ANN vs brute-force; memory footprint;
  kết luận trung thực: ở 50k×384 CPU, **chi phí encode truy vấn ~200ms chi phối** nên ANN chưa thấy
  lợi thế (chỉ để scale hàng triệu item); cross-encoder là nút thắt p99 → LTR thay thế rẻ hơn ~N×.
- `evaluate_human.py`: Cohen's Kappa auto vs người + pooled ranking eval trên test người gán.
- `adapt_real_data.py`: adapter pandas cho dataset Kaggle thật (Coursera/Udemy…): map cột theo alias,
  lọc IT, khử trùng lặp → `it_learning_items_real.csv` (không đụng synthetic) + đối chứng phân phối
  synthetic vs thật — trả lời chất vấn "dữ liệu giả".
- `run_all.py`: chạy toàn bộ pipeline đánh giá 1 lệnh (`--quick` cho CI).

**Tổng thể:** cách tiếp cận đánh giá ở mức chuẩn của paper/industry IR — có ablation, có significance,
có beyond-accuracy, có off-policy, có human-label, có chống leakage, và người viết tự nhận diện được
hạn chế trong chính báo cáo đầu ra (tables.md có lời giải thích các bảng "sạch" chạm trần lexical).

---

## 6. Luồng vận hành (build → serve)

```
generate_items.py  →  var/data/it_learning_items.csv
        │
build_model.py     →  artifacts/{item_list,tfidf_vectorizer,tfidf_matrix,retrieval_model}.pkl
build_embeddings.py →  artifacts/{embeddings,search_meta,char_vectorizer,char_matrix}.pkl + ann_index.faiss (nếu FAISS/hnswlib có)
generate_interactions.py → var/data/interactions.csv
build_cf.py        →  artifacts/cf_model.pkl
        │
python -m itlr.api (uvicorn) → FastAPI + UI tĩnh;  eval/run_all.py → reports/*
```

Cấu hình model qua env: `EMBEDDING_MODEL` (minilm/e5-base*/e5-large/bge-m3), `RERANKER_MODEL`,
`DISABLE_RERANKER`, `OPENAI_API_KEY`/`OPENAI_MODEL`, `OLLAMA_*`, `USE_OLLAMA`, `HF_HUB_OFFLINE`,
`ITLR_ITEMS_CSV`/`ITLR_INTERACTIONS_CSV`.

---

## 7. Vấn đề phát hiện (điểm cần lưu ý khi dùng/chạy)

1. **Layout "scripts/eval" đã đổi thành `eval/` khiến path trong script vỡ**: các file `eval/*.py`
   đều tính `sys.path ROOT = dirname(dirname(dirname(__file__)))` (đúng cho `scripts/eval/x.py`,
   sai cho `eval/x.py` — bây giờ trỏ lên 1 cấp ngoài repo) và `run_all.py` gọi lệnh
   `scripts/eval/...` + `cwd=ROOT` sẽ sai. Dấu hiệu file bị di chuyển từ `scripts/eval/` sang `eval/`
   mà không cập nhật path (các comment STALE: "python scripts/build_all.py", "scripts/eval/run_all.py").
2. **`itlr/core/ann.py` dùng đường dẫn tương đối "artifacts/"… không theo `config.ARTIFACTS_DIR`
   (= ROOT/var/artifacts/)**: `load_engine()` gọi `load_ann()` mặc định → nạp ANN KHÔNG THÀNH từ layout
   chuẩn (engine vẫn chạy — fallback brute-force matmul) — mâu thuẫn triết lý "độc lập CWD" của
   config.py. nên sửa `load_ann(config.ARTIFACTS_DIR)`.
3. **Snapshot chưa build artifacts**: `var/artifacts/`, `reports/`, `var/data/eval/` không tồn tại →
   app/API/eval chưa chạy được ngay; phải build pipeline trước (và lưu ý vấn đề #1 khi chạy eval/).
4. `opencode_client.py` dead code (không ai refer; cũng không bắt kịp branch LLM nào).
5. `load_engine()` mở file pickle bằng pickle.load(open(...)) không đóng — nhỏ (Windows file lock,
   descriptor leak tái nạp /admin/reload).
6. Không README, không pyproject/requirements.txt, không test tự động, không git — reproducibility
   phụ thuộc env; các artifact pickle scikit-learn nhạy cảm phiên bản (runtime_patches còn comment mơ).
7. Front-end `orbital-timeline.{css,js}` mới nhưng `index.html` vẫn nhắc tên tab cũ — UI đang
   chuyển giao; chưa duyệt sâu phần này.

---

## 8. Đánh giá ngắn

- **Thuật toán**: hướng chuẩn hiện đại — hybrid dense/sparse (E5 + char n-gram bỏ dấu), RAG-Fusion RRF,
  cross-encoder, MMR, ANN FAISS, multi-stage funnel, CF item-based, LTR LambdaMART, off-policy IPS/SNIPS/DR.
- **Kỹ thuật phần mềm**: cấu trúc package gọn, fail-safe có ý thức, comment giải thích *vì sao* đậm,
  xử lý tiếng Việt kỹ (normalize NFC, strip dấu, bigram/trigram, Porter stem cho ASCII).
- **Khoa học**: khung đánh giá là phần nổi bật nhất — nhiều kỹ thuật phòng chống tự lừa dối
  (anti-circular labeling, leakage-free CF split, off-policy với ground-truth kiểm chứng, mù nhãn
  human-eval, significance test, và chủ động nhận diện trần trong báo cáo).
- **Trạng thái**: mẫu nguồn (source snapshot) đã tái cấu trúc (streamlit→FastAPI, scripts→package) nhưng
  chưa hoàn tất di chuyển path (§7.1–7.2) và chưa build artifacts tại máy này.
