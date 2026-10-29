# Dữ liệu và quyền sử dụng

**ITLR–RAG | Intelligent IT Learning Platform** giữ riêng snapshot tài liệu thật, catalog legacy synthetic và dữ liệu đánh giá. Nguồn nhãn quyết định phạm vi có thể kết luận; kích thước snapshot không đại diện cho số tài nguyên đang phục vụ.

## Snapshot curated

[curated_resources.jsonl](curated_resources.jsonl) chứa **118 trang tài liệu thật** được chọn từ allowlist **128 URL** trong [cấu hình curated](../configs/curated.resources.json). Mười tài nguyên có tiêu đề trùng hoặc redirect được loại khi chuẩn hóa. Đây không phải dữ liệu synthetic và không phải tập evaluation đã được người dùng gán nhãn.

Mỗi hàng giữ URL gốc, tác giả/license, văn bản nguồn, thời điểm thu thập và `crawl_hash` SHA256 nguồn. `snapshot_text_sha256` kiểm tra văn bản chuẩn hóa đã lưu; khoảng trắng cuối có thể khác bytes nguồn ban đầu. Nội dung được trích xuất từ HTML, loại navigation và giới hạn **12.000 ký tự**; không sinh văn bản bằng LLM. Không tự tạo ngày xuất bản khi nguồn không có.

## Attribution và giấy phép bên thứ ba

| Nguồn | Attribution và điều kiện được giữ |
|---|---|
| Python documentation | © Python Software Foundation; PSF License Version 2; [giấy phép nguồn](https://docs.python.org/3/license.html) |
| MDN documentation | Mozilla Contributors; CC-BY-SA 2.5 hoặc mới hơn; văn bản MDN tái sử dụng tiếp tục theo giấy phép đó; [attribution và license](https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license) |
| Docker documentation | Docker documentation contributors; Apache License 2.0; [giấy phép nguồn](https://github.com/docker/docs/blob/main/LICENSE) |

Bản sao license nằm trong [licenses/](licenses/). URL nguồn gốc được giữ ở từng tài nguyên. Quyền sử dụng của dữ liệu áp dụng theo từng hàng, tách khỏi mã ứng dụng; không suy ra toàn repository mang MIT hoặc một giấy phép duy nhất. Điều kiện crawl mới phải được kiểm tra riêng theo [ADR-006](../docs/decisions/ADR-006-data-sources-licensing.md).

## Khôi phục và cập nhật

Snapshot dùng cho bootstrap offline có thể tái lập. Các lệnh sau ghi SQLite/catalog/artifacts; chạy trên môi trường đã chọn, không dùng như bước kiểm tra chỉ đọc:

```bash
.venv/bin/python scripts/import_curated_snapshot.py
.venv/bin/python scripts/build_all_v2.py --real-only --no-activate
```

Builder cần E5 cache, hoặc `--online` khi chủ động cho phép tải model. Sau probe, quyết định activate/reload theo [deployment](../deploy/DEPLOY.md), rồi export catalog bằng `scripts/export_web_catalog.py`. Web `npm run seed` dùng cho bootstrap, `npm run sync` đồng bộ catalog vào database đã cấu hình. Không xóa volume/database để cập nhật.

Thu thập mới phải giới hạn nguồn và số lượng, lưu timestamp/hash/license cùng báo cáo lượt chạy. Rolling feed không phải inventory đầy đủ; vắng khỏi feed không chứng minh tài liệu đã bị xóa.

## Synthetic và dữ liệu đánh giá

Catalog legacy 5.000 items, interactions CF 1.800 users seed 7 và các snapshot tương tác cũ là synthetic. Chúng phục vụ tái lập nghiên cứu và minh họa CF, không đại diện cho hành vi người thật. Dùng `--real-only` cho index chỉ chứa nguồn thật; builder mặc định có thể ghép legacy với dữ liệu crawl.

Qrels legacy được sinh từ metadata/rule-based; `--simulate-human` tạo nhãn mô phỏng. Qrels item tự soạn trên snapshot cũng không phải nhãn passage độc lập. Xem [ADR-003](../docs/decisions/ADR-003-synthetic-interactions-policy.md), [ADR-004](../docs/decisions/ADR-004-evaluation-design.md) và [validation](../reports/VALIDATION.md) trước khi diễn giải metric.
