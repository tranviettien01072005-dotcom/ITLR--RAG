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

import hashlib
import re
import json
import os
import shutil
import time
import uuid
from itlr.locking import artifact_locked
from pathlib import Path

from itlr import config

HISTORY_FILE = "CURRENT.json.history.json"
PROBE_OK = "ok"


class VersionError(RuntimeError):
    """Lỗi thiết lập/kích hoạt phiên bản index."""


def _dir(root: Path, version: str) -> Path:
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", version):
        raise VersionError("Invalid artifact version identifier")
    candidate = Path(root) / "versions" / version
    if not candidate.resolve().is_relative_to(Path(root).resolve()):
        raise VersionError("Artifact version escapes trusted root")
    return candidate


def create_version_dir(root=None, version: str | None = None) -> Path:
    """Tạo thư mục phiên bản build (staging). Trả về đường dẫn thư mục."""
    from itlr.versioning import _id

    root = Path(root or config.ARTIFACTS_DIR)
    version = version or (_id() + "-" + uuid.uuid4().hex[:12])
    d = _dir(root, version)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _id(now: float | None = None) -> str:
    """ID phiên bản = timestamp locale giây — đủ phân biệt giữa các lượt build."""
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now or time.time()))

def write_manifest(version_dir, manifest: dict) -> None:
    vdir = Path(version_dir)
    manifest = {**manifest, "sha256": artifact_hashes(vdir), "integrity_schema": 1}
    (vdir / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


MANIFEST = "MANIFEST.json"


def artifact_hashes(version_dir) -> dict[str, str]:
    """Local build integrity, not authentication: the artifact directory must be trusted."""
    hashes = {}
    for p in sorted(Path(version_dir).iterdir()):
        if p.name == MANIFEST:
            continue
        if p.is_symlink():
            raise VersionError("Symlink artifacts are not allowed")
        if p.is_file():
            with p.open("rb") as stream:
                hashes[p.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return hashes


def verify_integrity(version_dir, *, required=False) -> None:
    p = Path(version_dir) / MANIFEST
    if not p.exists() and not required:
        return  # Legacy local builds; production must require a manifest.
    try:
        manifest = json.loads(p.read_text(encoding="utf-8"))
        if manifest.get("integrity_schema") != 1 or manifest.get("sha256") != artifact_hashes(version_dir):
            raise VersionError("Artifact integrity mismatch; rebuild and probe trusted artifacts")
    except (OSError, ValueError, TypeError) as exc:
        raise VersionError("Invalid artifact integrity manifest") from exc


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
    pointer = root / "CURRENT.json"
    if not pointer.exists():
        return root
    try:
        meta = json.loads(pointer.read_text(encoding="utf-8"))
        candidate = _dir(root, meta["version"])
        if meta.get("dir") != f"versions/{meta['version']}" or not candidate.is_dir():
            raise VersionError("Invalid active artifact directory")
        return candidate
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise VersionError("Invalid artifact pointer") from exc


def _write_pointer(root: Path, version: str, event="activate") -> None:
    root = Path(root)
    hist = read_history(root)
    hist.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "event": event, "version": version})
    meta = {"version": version, "dir": f"versions/{version}", "history": hist[-200:]}
    tmp = root / f".CURRENT.json.tmp{os.getpid()}"
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, root / "CURRENT.json")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _append_history(root: Path, event: str, version: str | None) -> None:
    # Compatibility mirror; CURRENT.json is the authoritative atomic transaction.
    root = Path(root)
    tmp = root / f".{HISTORY_FILE}.tmp{os.getpid()}"
    tmp.write_text(json.dumps(read_history(root), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, root / HISTORY_FILE)


@artifact_locked
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
    verify_integrity(d, required=True)
    prev = current_version(root)
    _write_pointer(root, version)
    _append_history(root, "activate", version)
    return version


def history_prev_version(root=None):
    root = Path(root or config.ARTIFACTS_DIR)
    hist = read_history(root)
    cur = current_version(root)
    transitions = [h["version"] for h in hist
                   if h.get("event") in {"activate", "rollback"} and h.get("version")]
    for version in reversed(transitions):
        if version != cur:
            return version
    return None


@artifact_locked
def rollback(root=None) -> bool:
    """Quay về phiên bản activate trước — trả True nếu có và đã quay thành công."""
    root = Path(root or config.ARTIFACTS_DIR)
    prev = history_prev_version(root)
    if not prev:
        return False
    d = _dir(root, prev)
    if not probe_ok(d):
        raise VersionError("Previous artifact version has no successful probe")
    verify_integrity(d, required=True)
    cur = current_version(root)
    _write_pointer(root, prev, "rollback" if cur else "activate")
    _append_history(root, "rollback" if cur else "activate", prev)
    return True


def read_history(root=None) -> list[dict]:
    root = Path(root or config.ARTIFACTS_DIR)
    pointer = root / "CURRENT.json"
    if pointer.exists():
        try:
            meta = json.loads(pointer.read_text(encoding="utf-8"))
            if "history" in meta:
                if not isinstance(meta["history"], list):
                    raise VersionError("Invalid pointer history")
                return meta["history"]
        except (OSError, ValueError, TypeError) as exc:
            raise VersionError("Invalid artifact pointer history") from exc
    try:
        return json.loads((root / HISTORY_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        raise VersionError("Invalid legacy artifact history") from exc


@artifact_locked
def garbage_collect(root=None, keep: int = 3) -> None:
    """Giới hạn số phiên bản lưu trữ để tiết kiệm ổ cứng (mặc định giữ 3 gần nhất)."""
    root = Path(root or config.ARTIFACTS_DIR)
    cur = current_version(root)
    previous = history_prev_version(root)
    versions = [v for v in list_versions(root) if probe_ok(_dir(root, v))]
    for name in versions[keep:]:
        if name in {cur, previous}:
            continue  # không thể xóa phiên bản đang chạy
        shutil.rmtree(_dir(root, name), ignore_errors=True)
