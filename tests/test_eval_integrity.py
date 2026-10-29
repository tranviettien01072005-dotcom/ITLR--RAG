"""Regression: tính trung thực của evaluation (nhãn, rerank, exit code, provenance).

Các lỗi gốc được khóa lại ở đây:
  1. `run_all.py` luôn chạy `--simulate-human` -> ghi đè `human_judgments.csv` (nhãn thật).
  2. Bảng ablation vẫn có dòng "+ Cross-Encoder" y hệt "+ L1 hybrid signals" khi rerank tắt.
  3. Báo cáo trỏ sai `tables_noisy.md` cho benchmark có tag; không ghi nguồn qrels.
  4. `make_judgments.py` không bảo vệ nhãn người đã gán.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from itlr import config  # noqa: E402


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


make_judgments = _load("eval_make_judgments", "eval/make_judgments.py")
run_evaluation = _load("eval_run_evaluation", "eval/run_evaluation.py")
run_all = _load("eval_run_all", "eval/run_all.py")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def _pool() -> list[dict]:
    return [{"query_id": "Q001", "query": "học máy", "item_id": 1,
             "auto_grade": 2, "human_label": ""}]


def test_simulated_human_never_targets_real_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    real_rel = make_judgments.HUMAN_JUDGMENTS
    sim_rel = make_judgments.SIMULATED_HUMAN_JUDGMENTS
    assert real_rel != sim_rel

    _write_csv(tmp_path / real_rel, [{"query_id": "Q001", "query": "x", "item_id": 1,
                                      "auto_grade": 2, "human_label": "1"}])
    before = (tmp_path / real_rel).read_text(encoding="utf-8")

    out = make_judgments.write_human_pool(
        make_judgments.human_output_relpath(True), _pool(), simulate=True)
    assert Path(out) == tmp_path / sim_rel
    assert (tmp_path / sim_rel).is_file()
    assert (tmp_path / real_rel).read_text(encoding="utf-8") == before


def test_refuses_to_overwrite_real_human_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    path = tmp_path / make_judgments.HUMAN_JUDGMENTS
    _write_csv(path, [{"query_id": "Q001", "query": "x", "item_id": 1,
                       "auto_grade": 2, "human_label": "1"}])

    with pytest.raises(FileExistsError, match="từ chối ghi đè"):
        make_judgments.write_human_pool(
            make_judgments.HUMAN_JUDGMENTS, _pool(), simulate=False)
    assert make_judgments.count_labeled_rows(str(path)) == 1

    # --force mới được phép tạo lại khung.
    make_judgments.write_human_pool(
        make_judgments.HUMAN_JUDGMENTS, _pool(), simulate=False, force=True)
    assert make_judgments.count_labeled_rows(str(path)) == 0


def test_run_all_default_does_not_simulate_or_mix_qrels():
    args = argparse.Namespace(quick=False, with_ltr=False, with_keyword=False,
                              no_rerank=False, simulate_human=False)
    steps = run_all.build_steps(args)
    flat = [" ".join(s) for s in steps]
    assert not any("--simulate-human" in s for s in flat)

    clean = next(s for s in steps if s[0] == "eval/run_evaluation.py" and "--noisy" not in s)
    noisy = next(s for s in steps if s[0] == "eval/run_evaluation.py" and "--noisy" in s)
    assert "--judgments" not in clean and "--judgments" not in noisy  # cùng default qrels
    assert "--no-rerank" not in clean and "--no-rerank" not in noisy


def test_run_all_quick_and_simulate_are_explicit():
    args = argparse.Namespace(quick=True, with_ltr=False, with_keyword=True,
                              no_rerank=False, simulate_human=True)
    steps = run_all.build_steps(args)
    flat = [" ".join(s) for s in steps]
    assert any("--simulate-human" in s for s in flat)
    evals = [s for s in steps if s[0] == "eval/run_evaluation.py"]
    assert evals and all("--no-rerank" in s for s in evals)
    assert any("_kw" in s for s in flat)


def test_effective_configs_drop_rerank_only_row():
    configs, effective = run_evaluation.effective_configs(no_rerank=True, reranker_available=True)
    assert effective is False
    assert "+ Cross-Encoder" not in configs
    assert not any(c.use_rerank for c in configs.values())
    assert any("(no rerank)" in name for name in configs)

    configs2, effective2 = run_evaluation.effective_configs(
        no_rerank=False, reranker_available=False)
    assert effective2 is False and "+ Cross-Encoder" not in configs2

    configs3, effective3 = run_evaluation.effective_configs(
        no_rerank=False, reranker_available=True)
    assert effective3 is True
    assert "+ Cross-Encoder" in configs3
    assert configs3["+ Cross-Encoder"].use_rerank is True


def test_tables_and_provenance_are_honest(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    qrels_rel = "eval/relevance_judgments.csv"
    qrels = tmp_path / "data" / qrels_rel
    _write_csv(qrels, [{"query_id": "Q001", "query": "x", "category": "AI",
                        "topic": "ml", "item_id": 1, "grade": 2}])

    results = {
        "TF-IDF only": {"P@5": 0.1, "R@5": 0.2, "NDCG@10": 0.3, "MAP": 0.4,
                        "MRR": 0.5, "R@100": 0.6},
        "+ L1 hybrid signals": {"P@5": 0.2, "R@5": 0.3, "NDCG@10": 0.4, "MAP": 0.5,
                                "MRR": 0.6, "R@100": 0.7},
    }
    run_evaluation.write_tables(
        results, [], {"coverage": 0.5}, "+ L1 hybrid signals", 1, "_kw_noisy", True,
        judgments_path="eval/relevance_keyword.csv",
        rerank_requested=False, rerank_available=True, rerank_effective=False)

    table = (tmp_path / "reports" / "tables_kw_noisy.md").read_text(encoding="utf-8")
    assert "TẮT" in table                          # rerank tắt được nói rõ
    assert "KHÔNG phải nhãn người" in table
    assert "eval/relevance_keyword.csv" in table
    assert "| + Cross-Encoder |" not in table

    run_evaluation.write_tables(
        results, [], {"coverage": 0.5}, "+ L1 hybrid signals", 1, "_kw", False,
        judgments_path="eval/relevance_keyword.csv")
    clean = (tmp_path / "reports" / "tables_kw.md").read_text(encoding="utf-8")
    assert "tables_kw_noisy.md" in clean  # cross-ref đúng tag, không hardcode

    prov = run_evaluation.write_provenance(
        "_kw", judgments_path=qrels_rel, n_queries=1, rerank_requested=False,
        rerank_available=True, rerank_effective=False,
        configs=["TF-IDF only"], max_queries=0, noisy=True)
    data = json.loads(Path(prov).read_text(encoding="utf-8"))
    assert data["rerank_effective"] is False
    assert data["qrels_sha256"] and len(data["qrels_sha256"]) == 64
    assert data["n_queries"] == 1
    assert "KHÔNG phải nhãn người" in data["labels"]
