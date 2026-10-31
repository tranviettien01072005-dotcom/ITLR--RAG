"""Nạp & kiểm duyệt cấu hình NỒNG nguồn thu thập (configs/collect.sources.json).

Config nêu rõ nguồn được phép, giấy phép, chính sách full-text; validate rớt ngay
khi cấu hình sai (fail-fast trong lần chạy, không âm thầm bỏ nguồn).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from itlr import config


class SourcesError(ValueError):
    """Cấu hình nguồn không hợp lệ."""


@dataclass
class Source:
    source_id: str
    kind: str                 # "api" | "rss" | "web"
    name: str
    platform: str
    homepage: str
    full_text_allowed: bool   # False → chỉ lưu title + description + URL (snippet-only)
    license: str
    lang: str = "en"
    type_label: str = "Tài liệu"
    level_label: str = "Trung cấp"
    max_items_per_run: int = 25
    # API
    list_url: str | None = None
    fields: dict = field(default_factory=dict)
    # RSS
    feed_url: str | None = None
    # WEB
    list_urls: tuple[str, ...] = ()
    link_prefix: str | None = None
    link_pattern: str | None = None   # regex bắt buộc toàn bộ path (lọc trang mục lục)
    listing_is_complete: bool = False  # True only for authoritative full inventories.


    def as_dict(self) -> dict:
        """Dict cho bảng SQLite sources (provenance metadata)."""
        import json as _json

        return {
            "source_id": self.source_id,
            "kind": self.kind,
            "name": self.name,
            "platform": self.platform,
            "homepage": self.homepage,
            "full_text_allowed": int(self.full_text_allowed),
            "license": self.license,
            "lang": self.lang,
            "type_label": self.type_label,
            "level_label": self.level_label,
            "extras_json": _json.dumps({
                "max_items_per_run": self.max_items_per_run,
                "list_url": self.list_url,
                "feed_url": self.feed_url,
                "list_urls": list(self.list_urls),
                "link_pattern": self.link_pattern,
                "listing_is_complete": self.listing_is_complete,
            }, ensure_ascii=False),
            "updated_at": "",
        }


@dataclass
class SourceSet:
    defaults: dict
    sources: tuple[Source, ...]

    def ids(self) -> list[str]:
        return [s.source_id for s in self.sources]


KINDS = ("api", "rss", "web")


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SourcesError(f"Không tìm thấy file cấu hình nguồn: {path}")
    except json.JSONDecodeError as exc:
        raise SourcesError(f"JSON cấu hình nguồn hỏng: {path}: {exc}")


def load_sources(path=None, only=None) -> SourceSet:
    """Nạp config; `only` lọc theo source_id (dẫn hướng qua --sources CLI)."""
    path = Path(path or config.COLLECT_SOURCES)
    data = _load_json(path)
    defaults = dict(data.get("defaults") or {})
    raw_list = data.get("sources") or []
    if not raw_list:
        raise SourcesError("Cấu hình nguồn trống (sources: []).")

    sources = []
    seen_ids: set[str] = set()
    for raw in raw_list:
        s = _one_source(raw, defaults)
        if s.source_id in seen_ids:
            raise SourcesError(f"source_id bị trùng: {s.source_id}")
        seen_ids.add(s.source_id)
        if only and s.source_id not in only:
            continue
        sources.append(s)
    if only:
        unknown = set(only) - (seen_ids & set(only))
        if unknown:
            raise SourcesError(f"--sources không tồn tại trong config: {sorted(unknown)}")
    if not sources:
        raise SourcesError("Không nguồn nào hợp lệ sau khi lọc.")
    return SourceSet(defaults=defaults, sources=tuple(sources))


def _one_source(raw: dict, defaults: dict) -> Source:
    def req(key, tp=str):
        v = raw.get(key)
        if v is None or not isinstance(v, tp) or (isinstance(v, str) and not v.strip()):
            raise SourcesError(f"Nguồn thiếu/không hợp lệ trường '{key}': {raw.get('source_id', '?')}")
        return v

    sid = req("source_id")
    kind = req("kind")
    if kind not in KINDS:
        raise SourcesError(f"source '{sid}': kind phải là một trong {KINDS}")
    def policy_flag(key):
        value = raw.get(key, False)
        if not isinstance(value, bool):
            raise SourcesError(f"source {sid}: {key} must be a JSON boolean")
        return value

    full_text = policy_flag("full_text_allowed")
    listing_is_complete = policy_flag("listing_is_complete")

    def dflt(key, default=None):
        v = raw.get(key, defaults.get(key, default))
        return v

    fields = dict(raw.get("fields") or {})
    urls = [str(u) for u in (raw.get("list_urls") or [])]
    if kind == "api":
        if not raw.get("list_url"):
            raise SourcesError(f"source api '{sid}' cần list_url")
        for fkey in ("title", "url"):
            if fkey not in fields:
                raise SourcesError(f"source api '{sid}' cần fields.title & fields.url")
    if kind == "rss":
        if not raw.get("feed_url"):
            raise SourcesError(f"source rss '{sid}' cần feed_url")
    if kind == "web":
        if not urls:
            raise SourcesError(f"source web '{sid}' cần list_urls (list)")

    return Source(
        source_id=sid,
        kind=kind,
        name=req("name"),
        platform=raw.get("platform", sid),
        homepage=raw.get("homepage", ""),
        full_text_allowed=full_text,
        listing_is_complete=listing_is_complete,
        license=str(raw.get("license") or "unknown"),
        lang=str(dflt("lang", "en")),
        type_label=str(dflt("type_label", "Tài liệu")),
        level_label=str(dflt("level_label", "Trung cấp")),
        max_items_per_run=int(dflt("max_items_per_run", 25)),
        list_url=raw.get("list_url"),
        fields=fields,
        feed_url=raw.get("feed_url"),
        list_urls=tuple(str(u) for u in urls),
        link_prefix=raw.get("link_prefix"),
        link_pattern=raw.get("link_pattern") or None,
    )
