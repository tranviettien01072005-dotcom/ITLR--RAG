> Hướng dẫn đồ án / snapshot theo thời điểm. Giao diện chính là `web/` ở cổng 3000; xem [README](../README.md). Giữ nguyên thông báo bản quyền và provenance nguồn.

# Official learning-resource snapshot

`curated_resources.jsonl`:118 real documentation pages selected from the128-URL allowlist in
`configs/curated.resources.json`. Ten duplicate-title/redirect resources were removed during
normalization. This is **not synthetic** and is not a human-labelled evaluation dataset.
Every row records original URL/author/license, source text, retrieval timestamp and source SHA256. `snapshot_text_sha256` separately verifies the normalized stored text; trailing whitespace may differ from collected source bytes.
Text was extracted from HTML, navigation removed, and truncated at12,000 characters; no text
was generated. No source publication date is invented when unavailable.

Attribution and licenses apply per row, separately from application code:

- Python documentation © Python Software Foundation, PSF License Version2.
  https://docs.python.org/3/license.html
- MDN documentation by Mozilla Contributors, CC-BY-SA2.5 or later. Reused extracted MDN
  text remains under that license. https://developer.mozilla.org/en-US/docs/MDN/Writing_guidelines/Attrib_copyright_license
- Docker documentation by Docker documentation contributors, Apache License2.0.
  https://github.com/docker/docs/blob/main/LICENSE

License copies are in `licenses/`; original source links are preserved in every resource.
This snapshot supports reproducible local bootstrap; rerun bounded collection for updates,
or restore offline with `python scripts/import_curated_snapshot.py`, then `build_all_v2.py --real-only` and `export_web_catalog.py` / web `npm run sync`.
