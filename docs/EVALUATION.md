# Đánh giá: metric, dataset và giới hạn phương pháp

Mọi con số phải ghi rõ **ai tạo nhãn** và **đo cái gì**. Tài liệu này là nguồn chuẩn cho
cách đọc các báo cáo trong `reports/`; số cũ giữ nguyên tại báo cáo gốc.

## 1. Phân loại nhãn

| Loại | Nghĩa | Dùng được như |
|---|---|---|
| `human` | người thật chấm, có reviewer id | ground truth cho faithfulness/relevance |
| `heuristic` | luật máy (membership, n-gram, token overlap) | proxy, phải gọi là proxy |
| `synthetic` | sinh theo seed (interactions, simulate-human) | smoke test, không phải hành vi người |
| `AI-drafted` | AI soạn câu hỏi/claim | đề bài đánh giá, không phải nhãn đúng/sai |
| rule-based/metadata qrels | suy từ metadata nguồn | retrieval eval có kiểm soát, không phải human |

Không đổi nhãn AI thành `human`; chỉ tiêu chưa đo ghi `null`, không ghi 0%.

## 2. Retrieval

Bộ dữ liệu: 118 snapshot thật (`data/curated_resources.jsonl`), 1576 chunk; 23 query
release (VI/EN, nhiễu, nhiều bước); qrels **engineer-authored**, không phải panel độc lập.

| Metric | Định nghĩa | Cách đọc |
|---|---|---|
| Recall@5 | tỷ lệ query có item liên quan trong top 5 | phụ thuộc qrels; cao không đồng nghĩa trả lời đúng |
| MRR@5 | trung bình 1/rank của item liên quan đầu tiên | nhạy với vị trí top-1 |
| nDCG@5 | chuẩn hóa gain theo vị trí | cần mức gain; qrels hiện nhị phân |

Kết quả lịch sử: Recall@5 4,76% → 92,86% trên bộ 23 query; holdout end-to-end 83,33%,
tập xác nhận 62,50% ([release validation](../reports/RELEASE_VALIDATION_2026-10-30.md)).
Đây là số của bộ dữ liệu đó, không phải cam kết cho corpus mới.

Chạy lại:

```bash
.venv/bin/python eval/eval_release_retrieval.py --repeats 5 --out /tmp/release-retrieval.json
```

Lưu ý: ngưỡng `min_pct=84` được chọn trên dev judgments; `min_pct=90` giữ floor cũ.
Không đổi qrels/ngưỡng để nâng điểm.

## 3. Generation

Hai lớp đo tách biệt:

1. **Heuristic trên output** (`eval/eval_generation.py`): citation accuracy (id tồn tại +
   nằm trong context), hallucination-reference rate, groundedness proxy n-gram (n=3),
   relevancy proxy token overlap, refusal rate trên câu ngoài chủ đề. Đây là proxy, không
   phải entailment.
2. **Frozen blind eval** (`reports/release-readiness-evidence/blind_cases.jsonl`, SHA
   `2a3a98e2…`, 12 positive/8 negative, AI-authored, budget 45s): chấp nhận positive khi
   `generation_mode=llm_extractive`, `citation_validation.status=valid`,
   `evidence_binding=verbatim`, không có `generation_error`.

| Kết quả frozen (máy Linux) | Giá trị |
|---|---|
| Positive accepted | **11/12** (1 timeout 45,124s ở case `positive-06`) |
| Negative không tạo claim | **7/8** (2 template gate, 1 extractive search, 3 `no_selected_evidence`, 2 timeout) |
| Byte-verbatim join-check | **11/11** câu accepted |
| A/B prompt budget `800` | 11/12, mất `positive-12` → không promote |
| A/B prompt budget `500` | 10/12, mất `positive-07`,`positive-11` → không promote |
| SLO 45s với prompt đầy đủ | **FAIL** (prefill cold 40–51s trên CPU này) |

Không dùng HTTP 200, `done` hay citation hợp lệ để kết luận faithfulness. Chạy có chủ đích:

```bash
env -u DEEPSEEK_API_KEY -u OPENAI_API_KEY USE_OLLAMA=1 OLLAMA_MODEL=qwen2.5:3b \
  OLLAMA_TIMEOUT=45 DISABLE_RERANKER=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv/bin/python eval/eval_generation.py --llm
```

## 4. Human evaluation

Trạng thái: **NOT VERIFIED** — không có reviewer độc lập trong các phiên này.

- `reports/release-readiness-evidence/HUMAN_REVIEW_PROTOCOL.md`: thang 0–3 cho
  faithfulness, answer relevance, citation support, refusal appropriateness; quy ước
  human/AI-drafted/heuristic/LLM-judge; công thức unsupported-claim rate, citation
  precision, refusal accuracy.
- `human-review-packet.jsonl` (frozen 20 case): `human_* = null`.
- `human_eval_supplement.jsonl` (SHA `818e3b35…`): 20 case bổ sung — hard negatives, VI/EN,
  multi-hop, prompt injection — nhãn `AI-drafted scenario (not human)`.

Khi có nhãn người, dùng `eval/evaluate_human.py` cho Cohen's Kappa giữa nhãn tự động và
nhãn người (kiểm chất lượng qrels train), không thay thế chấm faithfulness.

## 5. CF, off-topic và các bộ khác

| Bộ | Nhãn | Ghi chú |
|---|---|---|
| `eval_cf.py`, `eval_off_policy.py` | synthetic seed 7 | đo cơ chế, không phải hiệu quả cá nhân hóa thật |
| `eval_offtopic.py` | rule-based | ngưỡng off-topic đã chọn trên dev |
| `report/latency.md` | đo máy | p50/p95 search/chat template; không phải SLO đã cam kết |
| `bench_latency.py` | đo thật | dùng cho benchmark prefill/decode; xem §12 certification |

## 6. Giới hạn phương pháp

- Cỡ mẫu nhỏ (20–23 query); không đủ cho CI thống kê hay p99 đáng tin.
- Câu hỏi/claim do AI soạn; chưa có người kiểm đề bài.
- Chỉ một annotator lịch sử; không có inter-annotator agreement thật.
- Citation validity/verbatim là kiểm tra cấu trúc, **không** phải entailment.
- Không dùng LLM-as-judge; nếu dùng sau này phải ghi model/prompt và vẫn không thay human.
- Không có đánh giá retrieval neural V3/CrossEncoder/generation trên bộ độc lập lớn.
- Không suy diễn kết quả staging thành production.
