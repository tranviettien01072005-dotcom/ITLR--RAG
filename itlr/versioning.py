"""Phiên bản hóa artifacts: build → kiểm thử → kích hoạt → rollback.

Vì sao: index mới cần chạy thử (probe) trước khi làm đụng API đang sống; khi có
sự cố phải quay về phiên bản gần nhất đã được chứng minh hoạt động.

Cơ chế (đơn giản, dễ debug — không symlink, không dịch vụ ngoài):
    var/artifacts/
        CURRENT.json                 # {version, dir} — KHÔNG kích hoạt phiên bản nào thì không có file này
        versions/<id>/...            # artifacts đầy đủ (đúng bộ artifact() mà engine nạp)
        CURRENT.json.history.json    # nhật ký activate/rollback (append)
Quy tắc:
    - `activate()` chỉ cho phép phiên bản CÓ MANIFEST ghi "probe": "ok" (đã kiểm thử).
    - Kích hoạt/rollback ghi file POINTER nguyên tử (tmp + os.replace) — engine nạp
      artifacts qua itlr.config.current_dir() nên thấy thay đổi ngay khi reload.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from itlr import config

HISTORY_FILE = "CURRENT.json.history.json"
PROBE_OK = "ok"


class VersionError(RuntimeError):
    """Lỗi thiết lập/kích hoạt phiên bản index."""


def _dir(root: Path, version: str) -> Path:
    return Path(root) / "versions" / version


def create_version_dir(root=None, version: str | None = None) -> Path:
    """Tạo thư mục phiên bản build (staging). Trả về đường dẫn thư mục."""
    from itlr.versioning import _id

    root = Path(root or config.ARTIFACTS_DIR)
    version = version or _id()
    d = _dir(root, version)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _id(now: float | None = None) -> str:
    """ID phiên bản = timestamp locale giây — đủ phân biệt giữa các lượt build."""
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))

def write_manifest(version_dir, manifest: dict) -> None:
    vdir = Path(version_dir)
    (vdir / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


MANIFEST = "MANIFEST.json"


def probe_ok(version_dir) -> bool:
    """True nếu manifest ghi probe == "ok" (bài kiểm thử index đã đạt)."""
    try:
        m = json.loads((Path(version_dir) / MANIFEST).read_text(encoding="utf-8"))
    except Exception:
        return False
    return m.get("probe") == PROBE_OK


def list_versions(root=None) -> list[str]:
    root = Path(root or config.ARTIFACTS_DIR)
    vdir = root / "versions"
    if not vdir.is_dir():
        return []
    out = [p.name for p in sorted(vdir.iterdir(), key=lambda p: p.name, reverse=True)
           if p.is_dir()]
    return out


def current_version(root=None) -> str | None:
    root = Path(root or config.ARTIFACTS_DIR)
    try:
        meta = json.loads((root / "CURRENT.json").read_text(encoding="utf-8"))
        return meta.get("version")
    except Exception:
        return None


def current_dir(root=None) -> Path:
    """Thư mục artifacts đang hoạt động: con trỏ CURRENT.json → dir, không con trỏ → root."""
    root = Path(root or config.ARTIFACTS_DIR)
    try:
        meta = json.loads((root / "CURRENT.json").read_text(encoding="utf-8"))
        d = meta.get("dir")
        if d:
            cand = Path(d)
            if not cand.is_absolute():
                cand = root / d
            if cand.is_dir():
                return cand
    except Exception:
        pass
    return root


def _write_pointer(root: Path, version: str) -> None:
    root = Path(root)
    meta = {"version": version, "dir": f"versions/{version}"}
    tmp = root / f".CURRENT.json.tmp{os.getpid()}"
    tmp.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, root / "CURRENT.json")


def _append_history(root: Path, event: str, version: str | None) -> None:
    root = Path(root)
    hist_path = root / HISTORY_FILE
    try:
        hist = json.loads(hist_path.read_text(encoding="utf-8")) if hist_path.exists() else []
    except Exception:
        hist = []
    hist.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "event": event, "version": version})
    tmp = root / f".{HISTORY_FILE}.tmp{os.getpid()}"
    tmp.write_text(json.dumps(hist[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, hist_path)


def activate(root=None, version: str | None = None) -> str:
    """Kích hoạt một phiên bản (đÃ phải probe ok). Con trỏ ghi nguyên tử."""
    root = Path(root or config.ARTIFACTS_DIR)
    version = version or current_version(root)
    if not version:
        raise VersionError("Không xác định được phiên bản để kích hoạt.")
    d = _dir(root, version)
    if not d.is_dir():
        raise VersionError(f"Thư mục phiên bản không tồn tại: {d}")
    if not probe_ok(d):
        raise VersionError(
            f"Phiên bản '{version}' CHỨA MANIFEST probe ok — chạy kiểm thử trước khi kích hoạt.")
    prev = current_version(root)
    _write_pointer(root, version)
    _append_history(root, "activate", version)
    return version


def history_prev_version(root=None):
    root = Path(root or config.ARTIFACTS_DIR)
    try:
        hist = json.loads((root / HISTORY_FILE).read_text(encoding="utf-8"))
    except Exception:
        return None
    activates = [h["version"] for h in hist if h.get("event") == "activate" and h.get("version")]
    if len(activates) >= 2:
        return activates[-2]
    return None


def rollback(root=None) -> bool:
    """Quay về phiên bản activate trước — trả True nếu có và đã quay thành công."""
    root = Path(root or config.ARTIFACTS_DIR)
    prev = history_prev_version(root)
    if not prev:
        return False
    cur = current_version(root)
    _write_pointer(root, prev)
    _append_history(root, "rollback" if cur else "activate", prev)
    return True


def read_history(root=None) -> list[dict]:
    root = Path(root or config.ARTIFACTS_DIR)
    try:
        return json.loads((root / HISTORY_FILE).read_text(encoding="utf-8"))
    except Exception:
        return []


def garbage_collect(root=None, keep: int = 3) -> None:
    """Giới hạn số phiên bản lưu trữ để tiết kiệm ổ cứng (mặc định giữ 3 gần nhất)."""
    root = Path(root or config.ARTIFACTS_DIR)
    cur = current_version(root)
    versions = list_versions(root)
    for name in versions[keep:]:
        if name == cur:
            continue  # không thể xóa phiên bản đang chạy
        shutil.rmtree(_dir(root, name), ignore_errors=True)
