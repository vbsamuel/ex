#!/usr/bin/env bash
set -euo pipefail

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1"; exit 1; }

export IEX_PROFILE="${IEX_PROFILE:-demo}"
export SAMPLE_YOUTUBE_URL="${SAMPLE_YOUTUBE_URL:-https://www.youtube.com/watch?v=dQw4w9WgXcQ}"

COMPOSE=(docker compose -f docker-compose.demo.yml)

"${COMPOSE[@]}" up -d || FAIL "docker compose up"
./scripts/provision_kafka_topics.sh || FAIL "provision kafka"
./scripts/provision_schema_registry.sh || FAIL "provision schema registry"
./scripts/provision_postgres.sh || FAIL "provision postgres"
./scripts/provision_minio.sh || FAIL "provision minio"

python -m src.services.orchestrator_service > /tmp/iex_orchestrator.log 2>&1 &
ORCH_PID=$!
python -m src.services.api_gateway > /tmp/iex_api.log 2>&1 &
API_PID=$!

cleanup() {
  kill "$ORCH_PID" "$API_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for i in {1..30}; do
  if curl -fsS http://localhost:8000/api/health > /dev/null 2>&1; then
    break
  fi
  sleep 1
  if [[ $i -eq 30 ]]; then
    FAIL "api health"
  fi
done

episode_id=$(curl -fsS -X POST http://localhost:8000/api/run \
  -H 'Content-Type: application/json' \
  -d "{\"youtube_url\":\"$SAMPLE_YOUTUBE_URL\"}" | python3 - <<'PY'
import json, sys
print(json.load(sys.stdin)["episode_id"])
PY
)

PASS "episode started $episode_id"

status=""
for i in {1..120}; do
  status=$(curl -fsS "http://localhost:8000/api/episode/$episode_id" | python3 - <<'PY'
import json, sys
print(json.load(sys.stdin)["status"])
PY
)
  if [[ "$status" == "COMPLETED" ]]; then
    break
  fi
  if [[ "$status" == "FAILED" ]]; then
    FAIL "episode failed"
  fi
  sleep 2
  if [[ $i -eq 120 ]]; then
    FAIL "episode timeout"
  fi
done
PASS "episode completed"

query_json=$(curl -fsS "http://localhost:8000/api/query?q=demo")
card_count=$(python3 - <<'PY'
import json, sys
print(len(json.loads(sys.stdin.read())["cards"]))
PY
<<<"$query_json")
if [[ "$card_count" -lt 1 ]]; then
  FAIL "/api/query returned no cards"
fi
PASS "/api/query returned cards"

cit_ok=$(python3 - <<'PY'
import json, sys
payload = json.loads(sys.stdin.read())
for c in payload.get("cards", []):
    for cit in c.get("citations", []):
        if "start_ms" in cit and "end_ms" in cit:
            print("ok")
            raise SystemExit(0)
print("no")
PY
<<<"$query_json")
if [[ "$cit_ok" != "ok" ]]; then
  FAIL "citations missing start_ms/end_ms"
fi
PASS "citations include start_ms/end_ms"

EU_COUNT=$(${COMPOSE[@]} exec -T postgres psql -U mini_brain -d mini_brain -tAc "select count(*) from core.evidence_units")
if [[ "$EU_COUNT" -lt 1 ]]; then
  FAIL "evidence_units count"
fi
PASS "evidence_units count > 0"

CC_COUNT=$(${COMPOSE[@]} exec -T postgres psql -U mini_brain -d mini_brain -tAc "select count(*) from core.context_cards where status='VERIFIED'")
if [[ "$CC_COUNT" -lt 2 ]]; then
  FAIL "verified context_cards count"
fi
PASS "verified context_cards >= 2"
