# Đánh giá cổng off-topic của chatbot

*Bộ test: 121 câu (60 IT / 61 ngoài lĩnh vực). Tín hiệu cổng = `query_relevance_max`.*

- **AUC (ROC) = 0.9825**
- Điểm TB: IT = 0.834 · ngoài lĩnh vực = 0.786

| Ngưỡng | Precision | Recall | F1 |
|---|---|---|---|
| 0.55 (hiện tại) | 0.496 | 1.000 | 0.663 |
| **0.800 (tối ưu F1)** | 0.881 | 0.983 | 0.929 |

### Bảng quét ngưỡng (trích)
| Ngưỡng | P | R | F1 |
|---|---|---|---|
| 0.40 | 0.496 | 1.000 | 0.663 |
| 0.45 | 0.496 | 1.000 | 0.663 |
| 0.50 | 0.496 | 1.000 | 0.663 |
| 0.55 | 0.496 | 1.000 | 0.663 |
| 0.60 | 0.496 | 1.000 | 0.663 |
| 0.65 | 0.496 | 1.000 | 0.663 |
| 0.70 | 0.496 | 1.000 | 0.663 |

*Kết luận: ngưỡng cổng được biện minh bằng **dữ liệu** (tối ưu F1 + AUC) thay vì cảm tính. Mở rộng bộ test -> con số đáng tin hơn.*