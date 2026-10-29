> **Ngữ cảnh đồ án — 2026-10-30:** Quyết định kiến trúc theo thời điểm. Không coi đây là chứng nhận thương mại hoặc trạng thái runtime hiện tại. Xem [README hiện tại](../../README.md).

# ADR-002: Đường dẫn artifact/data tập trung tại `itlr.config`, bỏ mặc định tương đối

## Trạng thái
Accepted

## Ngày
2026-10-27

## Bối cảnh
`itlr/core/ann.py` mặc định `artifacts_dir="artifacts"` (tương đối theo CWD) và nhiều script
trong `eval/` tính ROOT bằng `dirname(dirname(dirname(__file__)))` (×3) — trỏ ra NGOÀI repo.
Hậu quả: chạy từ thư mục khác (`python eval/run_all.py` từ nơi khác, hoặc service có cwd riêng)
thì engine nạp artifact nhầm/thiếu, `import itlr` hỏng, và server sức khỏe `/health` báo thiếu
artifact dù dữ liệu có thật trong `var/artifacts/`.

## Quyết định
- `itlr/config.py` là nguồn THẬT DUY NHẤT cho mọi đường dẫn: `ROOT`, `ARTIFACTS_DIR = ROOT/var/artifacts`,
  `DATA_DIR = ROOT/var/data`, hàm `artifact(name)`, `data_file(name)`, env override
  `ITLR_ITEMS_CSV`, `ITLR_INTERACTIONS_CSV`.
- `ann.build_ann/load_ann` đổi mặc định `artifacts_dir=None` → dùng `config.ARTIFACTS_DIR` lazily
  (monkeypatch được trong test); mọi `pickle.load/dump(open(...))` đổi sang `with`-block
  (engine.py, ann.py, build_model.py, build_embeddings.py, build_cf.py).
- `eval/*.py` tính ROOT bằng `dirname × 2`; `eval/run_all.py` gọi script theo path `eval/…`
  (trước đây là `scripts/eval/…`, đường dẫn cũ chết khi repo đổi cấu trúc).

## Phương án đã cân nhắc
- **Para `--artifacts` truyền tay qua hết mọi tầng**: tái tạo chính bug quên-truyền — bị loại.
- **ENV `ITLR_ARTIFACTS_DIR` thay config module**: KHÔNG bị loại hoàn toàn — config vẫn là
  nguồn đọc DUY NHẤT; env chỉ là ĐẦU VÀO của config (giống `ITLR_ITEMS_CSV`). Dùng để tách
  sandbox/multi-env; mặc định vẫn trung tâm `var/artifacts`.
- **Env cho `ITLR_ITEMS_CSV` / `ITLR_INTERACTIONS_CSV`**: giữ — data có thể thay ở runtime.

## Hệ quả
- Chạy được từ bất kỳ cwd nào: pytest, eval, uvicorn đều trúng cùng một thư mục artifacts.
- Bug tương đối-path bị chặn hồi quy bởi `tests/test_ann.py` (build/load từ cwd khác) và
  `tests/test_eval_scripts_paths.py` (import probe chạy từ ngoài repo).
- Đổi vị trí artifacts toàn cục = sửa 1 nơi (config); chưa có nhu cầu override kiểu multi-env.
