"""The real-snapshot lexical benchmark must stay runnable and honest."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_lexical_real_eval_runs_without_models(tmp_path):
    out = tmp_path / "eval.json"
    env = {**os.environ, "PYTHONUTF8": "1", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    run = subprocess.run(
        [sys.executable, str(ROOT / "eval" / "eval_lexical_real.py"), "--out", str(out)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=180,
    )
    assert run.returncode == 0, run.stderr[-800:]
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["queries"] == 8
    assert report["corpus_items"] == 118
    assert report["measured_requests"] == 160
    assert 0.0 <= report["recall_at_5"] <= 1.0
    assert report["faithfulness"] is None
    assert report["llm_calls"] == 0
