"""ITLR_ARTIFACTS_DIR may point at a versioned root; resolve CURRENT.json like the default."""
import json
from pathlib import Path

from itlr import config


def test_override_root_with_current_pointer_resolves_active_version(tmp_path, monkeypatch):
    version = tmp_path / "versions" / "v1"
    version.mkdir(parents=True)
    (tmp_path / "CURRENT.json").write_text(json.dumps({"version": "v1", "dir": "versions/v1"}))
    monkeypatch.setenv("ITLR_ARTIFACTS_DIR", str(tmp_path))
    assert config.current_dir() == version.resolve()


def test_override_flat_staging_dir_is_used_directly(tmp_path, monkeypatch):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "MANIFEST.json").write_text("{}")
    monkeypatch.setenv("ITLR_ARTIFACTS_DIR", str(staging))
    assert config.current_dir() == staging
