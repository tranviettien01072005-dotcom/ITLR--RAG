# ADR-007: Index theo phiên bản — build staging → probe → activate nguyên tử → rollback

## Trạng thái
Accepted

## Ngày
2026-10-29

## Bối cảnh
Xây lại index nghĩa là ghi đè artifacts mà API đang nạp: lỗi build (NaN, sai dim, hàng lệch)
làm chết server giữa chừng. Cần quy trình: index mới **chứng minh dùng được trước** khi tới tay
API, và quay lại được khi có sự cố — mà không cần dịch vụ ngoài hay symlink (dễ debug).

## Quyết định
Cấu trúc `var/artifacts/` (module `itlr/versioning.py`):

```
CURRENT.json                     # con trỏ {version, dir} — ghi Nguyên tử (tmp + os.replace)
CURRENT.json.history.json        # nhật ký activate/rollback (cắt tối đa 200 dòng)
versions/<YYYYMMDD-HHMMSS>/      # artifacts đầy đủ của một phiên bản + MANIFEST.json
```

- **Build vào staging**: `scripts/build_all_v2.py` build vào `versions/<id>/` mới, không đụng
  bản đang chạy.
- **Probe** (`itlr/indexv2.py`, 3 mức dần dần nặng):
  1. `validate_artifacts` — đủ file, hàng khớp (items = embeddings = char matrix), dim khớp,
     không NaN/Inf, L2-norm ≈ 1, item_id unique, `retrieval_model` đủ khóa.
  2. `self_retrieval_sanity` — TF-IDF tự-tìm-tiêu-đề ≥ 80% top-5 (30 sample, seed cố định).
  3. `engine_probe` — nạp engine THẬT (torch/faiss) trong subprocess riêng,
     `ITLR_ARTIFACTS_DIR=<staging>`, chạy một truy vấn; rc=0 mới qua.
  Kết quả ghi vào `MANIFEST.json` (`probe: "ok"|"fail"` + report chi tiết).
- **Activate**: chỉ được với phiên bản `probe: ok`. Con trỏ `CURRENT.json` ghi nguyên tử.
  `config.current_dir()` đọc con trỏ **mỗi lần gọi** (không cache) — mọi loader (`config.artifact`)
  chuyển đúng náb qua đó; không con trỏ ⇒ fallback `var/artifacts/` (hành vi cũ, tương thích ngược).
- **Rollback**: `versioning.rollback()` — ghi con trỏ về phiên bản activate liền trước
  (đọc từ history). Restart/reload là đủ; dữ liệu cũ vẫn nguyên trên đĩa.
- **GC**: sau activate, `garbage_collect(keep=3)` — giữ 3 phiên bản gần nhất, không bao giờ
  xóa phiên bản đang trỏ tới.

## Phương án đã cân nhắc
- **Ghi đè trực tiếp + backup .bak**: thời điểm copy chồng lấn server nạp → file nửa vời;
  rollback tốn do copy. Bị loại.
- **Symlink `current → versions/<id>`**: activate nhanh nhưng symlink + pickle tuyệt đối đường
  dẫn dễ nhầm, và một số tool follow-link tốn đạc. Con trỏ JSON dễ đọc hơn (biết version== nào).
- **DB/phục vụ từ index mới đã cùng nạp hot-swap trong process**: dùng nhiều RAM (2 index cùng
  lúc), phức tạp; chọn đơn giản: reload process/nạp lại con trỏ.

## Hệ quả
- Tự động hóa: `refresh_pipeline.py` → `build_all_v2.py` (probe Trong) — probe fail ⇒ không
  activate, index sống vẫn chạy (incident size = 0).
- Reset nhanh: xóa `CURRENT.json` ⇒ về trạng thái "không có phiên bản" (dùng artifacts gốc —
  tương thích cách build cũ).
- `MANIFEST.json` mỗi phiên bản là nhật ký các check đã qua — phân tích sự cố có bằng chứng.
- Chi phí đĩa: ~3 phiên bản artifacts (nhớ cấu hình `--keep`).
