#!/usr/bin/env bash
# Reliability/capacity tour on the isolated staging stack. Keeps volumes; never down -v.
set -uo pipefail
B=/tmp/opencode/itlr-docker-fresh
R=/tmp/opencode/itlr-reliability
COMPOSE=(docker compose --project-name itlr-resume-1031c --file "$B/compose.yml")
cd "$R" || exit 2

wait_health() {
  local until=$((SECONDS+$1))
  while (( SECONDS < until )); do
    if curl -fsS http://127.0.0.1:19081/health >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}

db_counts() {
  local name=$1
  "${COMPOSE[@]}" exec -T web node -e '
const {Pool}=require("pg");const p=new Pool({connectionString:process.env.DATABASE_URL});
(async()=>{const q=async s=>(await p.query(s)).rows[0];
const o={users:(await q("select count(*)::int n from users")).n,messages:(await q("select count(*)::int n from messages")).n,
conversations:(await q("select count(*)::int n from conversations")).n,courses:(await q("select count(*)::int n from courses")).n};
console.log(JSON.stringify(o));await p.end()})().catch(e=>{console.error(e.message);process.exitCode=1});' > "$R/$name.json" 2>"$R/$name.err"
}

{
  echo "=== cold start ==="
  start=$SECONDS
  "${COMPOSE[@]}" up -d postgres ollama observer api web caddy >/dev/null 2>&1
  wait_health 420 && echo "health_ready_s=$((SECONDS-start))" || echo "health_ready=FAILED"
  first=$(/home/o/ITLR--RAG/.venv/bin/python load.py conc --n 1 | tail -2)
  echo "$first"

  echo "=== concurrency ==="
  for n in 1 2 4; do
    /home/o/ITLR--RAG/.venv/bin/python load.py conc --n "$n" || echo "conc $n failed"
  done
  echo "=== concurrency 8 (retrieval/web path only) ==="
  for i in 1 2 3 4 5 6 7 8; do
    curl -s -o /dev/null -w "%{http_code} %{time_total}\n" -X POST http://127.0.0.1:19081/api/search \
      -H 'Content-Type: application/json' -d '{"query":"docker volumes","min_pct":84}' &
  done
  wait

  echo "=== soak ==="
  /home/o/ITLR--RAG/.venv/bin/python load.py soak --seconds 120 || echo "soak failed"
  echo "=== rss after soak ==="
  /home/o/ITLR--RAG/.venv/bin/python load.py rss

  echo "=== cancel ==="
  /home/o/ITLR--RAG/.venv/bin/python load.py cancel || echo "cancel failed"

  echo "=== db before crash ==="
  db_counts db-before-crash; cat "$R/db-before-crash.json"

  echo "=== crash recovery ==="
  api_id=$("${COMPOSE[@]}" ps -q api)
  kill -9 "$api_id" 2>/dev/null || true
  sleep 3
  crash_start=$SECONDS
  "${COMPOSE[@]}" up -d api >/dev/null 2>&1
  wait_health 420 && echo "recovery_s=$((SECONDS-crash_start))" || echo "recovery=FAILED"
  /home/o/ITLR--RAG/.venv/bin/python load.py health | tail -2

  echo "=== db after recovery ==="
  db_counts db-after-recovery; cat "$R/db-after-recovery.json"
  echo "=== final rss ==="
  /home/o/ITLR--RAG/.venv/bin/python load.py rss

  echo "=== stop (volumes retained) ==="
  "${COMPOSE[@]}" stop --timeout 45 >/dev/null 2>&1
  "${COMPOSE[@]}" ps -a --format '{{.Service}} {{.Status}}'
  ss -ltn | grep -E '19081|19444' || echo ports_closed
} > "$R/tour.log" 2>&1
echo "TOUR_DONE rc=$?"
