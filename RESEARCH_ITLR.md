# ITLR–RAG | Intelligent IT Learning Platform — Repository research

Historical analysis: **2026-10-27**, before the subsequent packaging, security, Web and V3 work.
The source snapshot contained 46 Python files (approximately 6,750 lines), two knowledge JSON
files, a static UI and two CSV datasets. Missing Git metadata, README, packaging, tests and
artifacts were observations about that snapshot; they are not the repository’s current state.
See [README](README.md), [project memory](docs/PROJECT_MEMORY.md),
[validation](reports/VALIDATION.md) and [V3 review](reports/V3_RESTRUCTURING_2026-10-30.md)
for later implementation and measured evidence.

## Product scope and architecture

ITLR–RAG supports IT learning through resource search, recommendations and a RAG chatbot.
The snapshot combined hybrid retrieval, Vietnamese query handling, concept/career knowledge,
optional LLM generation and item-based CF. It also contained evaluation code for ablation,
robustness, statistical comparisons, diversity, off-policy estimation and learning to rank.
Presence of a module did not establish its runtime quality or deployment readiness.

The current primary interface is Express + TypeScript + EJS with PostgreSQL in `web/`, port 3000.
FastAPI `itlr.api.server:app`, port 8000, provides retrieval/chat; its static UI is secondary.
Current chunk retrieval is shared through `itlr/retrieval/`; `itlr/core/chunks.py` owns FAISS
chunk ranking/RRF/passage reranking. Generation belongs to `itlr/chatbot/llm_client.py`.
Collection/pipelines and versioning/locking have separate responsibilities. The sections below
preserve the earlier design observations rather than prescribe a second architecture.

## Historical loading and retrieval paths

`load_engine()` loaded catalog `item_list.pkl`, lexical `retrieval_model.pkl`, embeddings and
`search_meta.pkl`, character vectorizer/matrix, then CF. It constructed SentenceTransformer,
ANN, optional CrossEncoder and `EducationalChatbot`. `RecommenderEngine` exposed `search`,
`chat`, `chat_stream`, `personas` and `for_you`. CF subsequently became optional in
[ADR-005](docs/decisions/ADR-005-cf-optional-decoupling.md).

| Snapshot ranking stage | Candidate scope and method |
|---|---|
| Candidate generation | 5,000 → approximately 600; embedding ANN and accent-stripped character n-grams, lexical alternatives, or query variants fused by RRF |
| L1 | TF-IDF 0.42; BM25 0.18; category 0.14; topic Jaccard 0.12; topic containment 0.06; title overlap 0.05; type 0.03 |
| L2 | Top 48 via `BAAI/bge-reranker-base` or optional LightGBM LambdaMART |
| Reorder | MMR λ=0.7 and related-category bonuses 0.55/0.35/0.15 |

Snapshot display gates were `ABS_RELEVANCE_GATE=0.48` and `ABS_ITEM_FLOOR=0.42`.
`calibrate_confidence` mapped scores into 90–100% with a t^0.7 curve without changing order.
That display transformation was not probabilistic calibration or measured user suitability.

`core/ann.py` supported FAISS/hnswlib and a brute-force path. `core/rag.py` combined TF-IDF,
BM25 and topic signals. The original BM25 implementation later moved into `itlr/retrieval/bm25.py`;
`itlr/core/bm25.py` remains a required import/pickle compatibility shim.

## Historical chatbot behavior

The inspected `chatbot.py` had 1,616 lines. Query handling corrected common typos and used
`difflib` cutoff 0.84 on tokens of at least four characters. It expanded abbreviations while
restricting ambiguous short tokens such as `ai`, `be` and `ui`. Follow-ups of at most eight words
could inherit context from two recent user turns.

The intent router handled definition, comparison, career path, skill gap, next skill, time
estimate, admin statistics, interview, salary and career guidance. Multi-clause routing split
question marks, semicolons and conjunctions. Knowledge included 360 concepts, 19 career roles,
a next-skill graph, six comparison pairs, learning-time rules and 13 career-selection suggestions.
Salary references were Vietnam 2024–25 content, not verified current market guidance.

An early off-topic gate used `query_relevance_max < 0.55`, with safe concept-alias exceptions.
Semantic multi-query search fused original/history/enriched variants with RRF, reranked top 32
once and applied MMR. `gate_query` kept expanded variants from inflating relevance. Category
selection used the top-five majority. Related-resource suggestions used item cosine/hybrid
signals from a pool of 300.

Generation initially used OpenAI `gpt-4o-mini` or locally detected Ollama `qwen2.5:3b`; template
mode offered learning paths, comparisons, search, recommendations and answers. Learning-path
selection used three stages (3–4–3), difficulty and category-aware backfill. LLM output was
requested to retain knowledge values and cite catalog resources. Provider logic was later
centralized with DeepSeek as configured primary in [ADR-001](docs/decisions/ADR-001-deepseek-primary-llm.md).
Prompt rules and valid IDs alone did not establish truth or semantic grounding.

FastAPI exposed health, metrics, search, chat, SSE, personas, for-you, suggested resources and
admin reload. SSE addressed long local-model responses: source notes cited 30–135 seconds per
answer and approximately 90-second cold starts; these were historical observations, not SLOs.
Later SSE contracts distinguish provisional tokens from the authoritative validated final answer.

CF used normalized item co-occurrence `R.T @ R`, cosine normalization `sqrt(pop_i * pop_j)`
and sparse top-50 neighbors. Empty history used popularity. Forty persona archetypes supported
interface tests; they did not represent measured users. Later settings and benchmark results
must be read from their own dated evidence.

## Historical data and provenance

| Snapshot | Recorded contents |
|---|---|
| `var/data/it_learning_items.csv` | 5,000 synthetic items: 2,493 courses / 2,507 documents; 26 categories; basic 2,001 / intermediate 1,850 / advanced 1,149; ten columns |
| `var/data/interactions.csv` | 12,342 synthetic interactions / 500 users; no timestamps |

Generators could target 50,000 items; that was not the observed corpus size. Item templates
included repeated translation-like phrases, with `clean_display_text` reducing repetition in
presentation. An earlier interaction generator used latent category/topic factors and 40 user
archetypes, with `P(click) ∝ exp(p_u·q_i)` and Pareto popularity bias, replacing popularity-only
sampling. A later pipeline generated 1,800 users with seed 7; see
[ADR-003](docs/decisions/ADR-003-synthetic-interactions-policy.md).

These datasets remain synthetic regardless of realistic labels or apparent co-occurrence.
Real snapshots now have a distinct source at `data/curated_resources.jsonl`; current item counts
must come from `/health` together with version/provenance. Source rights and attribution are
preserved under [ADR-006](docs/decisions/ADR-006-data-sources-licensing.md).

## Evaluation design observed

`itlr/eval/` implemented precision, recall, HitRate, MRR, MAP and graded nDCG with gain
`2^rel−1` / log2 discount, macro averaging, coverage, ILD, novelty, serendipity and Gini.
Statistical helpers included 10,000-sample paired bootstrap CI95, paired tests with scipy/z
fallbacks and Cohen’s kappa. Implementation and runtime evidence are separate concerns.

Retrieval qrels came from metadata topic/category rules over the full catalog, not from retrieved
rankings. Natural-language queries could mask English terms; noisy queries removed accents and
perturbed roughly 4–6% of characters. Seven ablation configurations covered TF-IDF, BM25,
hybrid lexical, E5, L1, CrossEncoder and RAG-Fusion/MMR. Human-label sheets hid automatic labels;
simulated labels only exercised that workflow. These measures reduce some leakage risks but do
not replace independent relevance judgments.

CF evaluation compared popularity and leave-one-out/temporal-style splits, retraining on train
only for the clean split. With no timestamps, row order was a time proxy rather than evidence
of real temporal behavior. Off-policy code covered IPS, SNIPS, doubly robust estimation,
bootstrap intervals, ESS and known synthetic rewards. Coverage of ground truth in a simulation
does not prove general unbiasedness or real user benefit.

LTR used 15 features, including lexical/dense/character/cross-encoder scores, category/topic
signals, type, length, popularity and level. Hard negatives were 70% near-miss / 30% random;
SHAP, calibration plots and holdout comparisons were available. Metadata-aligned heuristics could
approach nDCG≈1.0, limiting what LTR comparisons could establish.

Latency tooling measured p50/p95/p99, QPS and memory. Earlier notes discussed encoding around
200ms on a 50k×384 CPU setup and CrossEncoder cost; these were different configurations from
later E5/V3 measurements. No million-item capacity or automatic ANN advantage follows.
`adapt_real_data.py` mapped external datasets into a separate catalog with IT filtering and
deduplication; naming a source did not establish license permission or completed ingestion.
Generation citation checks must not be reported as faithfulness: unmeasured semantic metrics
remain `null`, as required by [ADR-004](docs/decisions/ADR-004-evaluation-design.md).

## Findings and subsequent direction

The initial snapshot had broken evaluation root paths, ANN’s CWD-relative artifact default,
unclosed pickle handles, missing local artifacts and inconsistent static-UI labels. A wrapper
`opencode_client.py` appeared unused in that analysis; deletion still requires caller/import
verification. Later review addressed paths, packaging, tests and provider boundaries; do not
reuse these initial observations as current defects. See [2026-10-27 review](docs/review-2026-10-27.md).

Current operation uses trusted builder artifacts, staging/probe/atomic pointer/rollback,
explicit admin authorization, and one service worker on local Linux storage. Historical
benchmarks establish only their own corpus/configuration. Independent passage qrels, generation
faithfulness, reranker/load validation and complete deployment exercises remain distinct evidence
gates. This research document was rewritten as documentation only; no new benchmark is claimed.
