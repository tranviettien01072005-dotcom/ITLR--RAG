#!/usr/bin/env bash
# Wrapper cho cron: nạp .env rồi chạy refresh pipeline (crawl → build V2 → probe → activate).
# Dùng với crontab như trong deploy/DEPLOY.md §1.3.
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ -f ".env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

exec .venv/bin/python scripts/refresh_pipeline.py "$@"
