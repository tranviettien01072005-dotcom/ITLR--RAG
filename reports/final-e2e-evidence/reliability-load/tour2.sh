set -uo pipefail
B=/tmp/opencode/itlr-docker-fresh
R=/tmp/opencode/itlr-reliability
C=(docker compose --project-name itlr-resume-1031c --file "$B/compose.yml")
cd "$R" || exit 2
"${C[@]}" up -d postgres ollama observer api web caddy >/dev/null 2>&1
for i in $(seq 1 200); do curl -fsS http://127.0.0.1:19081/health >/dev/null 2>&1 && break; sleep 2; done
echo "health=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:19081/health)"
/home/o/ITLR--RAG/.venv/bin/python load.py rss
for n in 1 2 4; do /home/o/ITLR--RAG/.venv/bin/python load.py conc --n "$n"; done
/home/o/ITLR--RAG/.venv/bin/python load.py cancel
/home/o/ITLR--RAG/.venv/bin/python load.py rss
"${C[@]}" stop --timeout 45 >/dev/null 2>&1
ss -ltn | grep -E '19081|19444' || echo ports_closed
