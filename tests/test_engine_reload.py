import pytest
from itlr import engine


def test_failed_reload_keeps_serving_previous_engine(tmp_path, monkeypatch):
    monkeypatch.setattr(engine.config,'ARTIFACTS_DIR',tmp_path)
    previous = object()
    monkeypatch.setattr(engine,'_load_engine',lambda:previous)
    engine.load_engine.cache_clear()
    assert engine.load_engine() is previous
    def fail(): raise FileNotFoundError('broken candidate')
    monkeypatch.setattr(engine,'_load_engine',fail)
    try:
        with pytest.raises(FileNotFoundError):
            engine.load_engine.reload()
        assert engine.load_engine() is previous
    finally:
        engine.load_engine.cache_clear()
