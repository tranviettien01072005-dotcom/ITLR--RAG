"""Tái lập TOÀN BỘ thực nghiệm bằng MỘT lệnh (reproducibility).

Chạy lần lượt: sinh qrels -> ablation sạch -> ablation nhiễu CÙNG qrels -> CF eval ->
off-policy -> ngưỡng off-topic -> Cohen's Kappa -> latency. Mọi con số trong reports/ tái
lập được từ đây.

Nguyên tắc trung thực:
  - KHÔNG tự chạy --simulate-human (nhãn mô phỏng chỉ để smoke-test, ghi file riêng).
  - Bảng sạch và bảng nhiễu dùng CÙNG một bộ qrels; chỉ truy vấn bị nhiễu.
  - Bước lỗi -> exit code 1 (CI không được coi là xanh khi eval fail).
  - Rerank mặc định BẬT; --no-rerank/--quick tắt và báo cáo phải ghi rõ (không giả vờ có
    tầng Cross-Encoder).

    python eval/run_all.py                  # bộ đầy đủ (chậm; rerank + mọi bước)
    python eval/run_all.py --quick          # rút gọn cho CI (tắt rerank)
    python eval/run_all.py --with-keyword   # thêm benchmark qrels từ khóa
    python eval/run_all.py --simulate-human # smoke-test nhãn mô phỏng (file riêng)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run(cmd, env):
    print(f"\n{'='*70}\n$ {' '.join(cmd)}\n{'='*70}")
    t = time.time()
    r = subprocess.run([sys.executable, *cmd], cwd=ROOT, env=env)
    print(f"[{'OK' if r.returncode == 0 else 'LỖI'}] {time.time()-t:.1f}s")
    return r.returncode


def build_steps(args) -> list[list[str]]:
    """Danh sách bước eval theo thứ tự phụ thuộc (hàm thuần để test được)."""
    quick = ["--quick"] if args.quick else []
    no_rerank = ["--no-rerank"] if (args.no_rerank or args.quick) else []

    steps: list[list[str]] = []

    # 1) Qrels chính (tự nhiên, không lộ token topic). Không sinh nhãn người giả.
    make_main = ["eval/make_judgments.py", "--natural", "--queries-per-cat", "4"]
    if args.simulate_human:
        make_main.append("--simulate-human")
    steps.append(make_main)

    # 2) Ablation sạch và nhiễu trên CÙNG bộ qrels (khác nhau chỉ ở truy vấn).
    steps.append(["eval/run_evaluation.py", *quick, *no_rerank])
    noisy = ["eval/run_evaluation.py", "--noisy", *quick, *no_rerank]
    steps.append(noisy)

    # 3) Benchmark phụ tùy chọn: qrels từ khóa (không ghi đè qrels chính).
    if args.with_keyword:
        steps.append(["eval/make_judgments.py", "--out", "eval/relevance_keyword.csv",
                      "--no-human"])
        steps.append(["eval/run_evaluation.py", "--judgments", "eval/relevance_keyword.csv",
                      "--tag", "_kw", "--noisy", *quick, *no_rerank])

    # 4) CF / off-policy / cổng off-topic / human / latency.
    steps.append(["eval/eval_cf.py", "--max-users", "300" if args.quick else "800"])
    steps.append(["eval/eval_off_policy.py", "--rounds", "3000" if args.quick else "6000"])
    steps.append(["eval/eval_offtopic.py"])
    steps.append(["eval/evaluate_human.py"])
    steps.append(["eval/bench_latency.py", "--repeats", "10" if args.quick else "30"])

    # LTR (tùy chọn) phải train TRƯỚC khi eval dùng nó.
    if args.with_ltr:
        steps.insert(2, ["eval/build_ltr.py", "--no-cross"])
    return steps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--with-ltr", action="store_true", help="Bao gồm train LTR (chậm)")
    ap.add_argument("--with-keyword", action="store_true",
                    help="Chạy thêm benchmark qrels từ khóa (tag _kw)")
    ap.add_argument("--no-rerank", action="store_true",
                    help="Tắt Cross-Encoder (báo cáo sẽ ghi rõ; --quick cũng tắt)")
    ap.add_argument("--simulate-human", action="store_true",
                    help="Smoke-test nhãn mô phỏng (ghi human_judgments_simulated.csv)")
    args = ap.parse_args()

    if args.no_rerank and args.with_ltr:
        print("[LỖI] --no-rerank và --with-ltr xung khắc (LTR cần đặc trưng cross-encoder).",
              file=sys.stderr)
        return 2

    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    steps = build_steps(args)
    failed = []
    for cmd in steps:
        if run(cmd, env) != 0:
            failed.append(cmd[0])

    print(f"\n{'='*70}\nTỔNG KẾT: {len(steps)-len(failed)}/{len(steps)} bước OK")
    if failed:
        print("Bước lỗi:", ", ".join(failed))
    print("Báo cáo ở: reports/  (tables.md, tables_noisy.md, cf_eval.md, off_policy.md, "
          "offtopic_eval.md, latency.md, human_eval.md, ltr.md)")
    if args.no_rerank or args.quick:
        print("[!] Rerank đã TẮT: bảng kết quả không có tầng Cross-Encoder thật.")
    if args.simulate_human:
        print("[!] Nhãn human trong lần chạy này là MÔ PHỎNG (file riêng) — không dùng báo cáo.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
