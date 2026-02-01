#!/usr/bin/env bash
set -euo pipefail

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1"; exit 1; }

export IEX_PROFILE="${IEX_PROFILE:-demo}"
export SAMPLE_YOUTUBE_URL="${SAMPLE_YOUTUBE_URL:-https://www.youtube.com/watch?v=jNQXAC9IVRw}"
export PYTHONPATH="/home/vsam/ex"
export OLLAMA_BASE="${OLLAMA_BASE:-http://localhost:11434}"
export OLLAMA_WRITER_MODEL="${OLLAMA_WRITER_MODEL:-gemma3:12b-it-qat}"
export OLLAMA_REVIEWER_MODEL="${OLLAMA_REVIEWER_MODEL:-deepseek-coder-v2:16b}"
export OLLAMA_EMBED_MODEL="${OLLAMA_EMBED_MODEL:-nomic-embed-text:latest}"

COMPOSE=(docker compose -f docker-compose.demo.yml)

"${COMPOSE[@]}" up -d || FAIL "docker compose up"
./scripts/provision_kafka_topics.sh || FAIL "provision kafka"
./scripts/provision_schema_registry.sh || FAIL "provision schema registry"
./scripts/provision_postgres.sh || FAIL "provision postgres"
./scripts/provision_minio.sh || FAIL "provision minio"

if ! curl -fsS "$OLLAMA_BASE/api/tags" > /tmp/iex_ollama_tags.json; then
  FAIL "ollama not reachable at $OLLAMA_BASE"
fi
for model in "$OLLAMA_WRITER_MODEL" "$OLLAMA_REVIEWER_MODEL" "$OLLAMA_EMBED_MODEL"; do
  if python3 -c 'import json,sys; data=json.load(open("/tmp/iex_ollama_tags.json")); names=[m.get("name","") for m in data.get("models",[])]; want=sys.argv[1]; match=any(n==want or n.startswith(want) or want.startswith(n) for n in names); print("ok" if match else "no"); sys.exit(0 if match else 1)' "$model"; then
    PASS "ollama model present: $model"
  else
    echo "WARN: ollama model not listed: $model (continuing)"
  fi
done

python3 -m pip install -r /home/vsam/ex/requirements.txt > /tmp/iex_pip.log 2>&1 || FAIL "pip install"

python3 -m src.services.orchestrator_service > /tmp/iex_orchestrator.log 2>&1 &
ORCH_PID=$!
python3 -m src.services.api_gateway > /tmp/iex_api.log 2>&1 &
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
    echo "--- api log ---"
    tail -n 200 /tmp/iex_api.log || true
    echo "--- orchestrator log ---"
    tail -n 200 /tmp/iex_orchestrator.log || true
    FAIL "api health"
  fi
done

episode_id=$(curl -fsS -X POST http://localhost:8000/api/run \
  -H 'Content-Type: application/json' \
  -d "{\"youtube_url\":\"$SAMPLE_YOUTUBE_URL\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["episode_id"])')

PASS "episode started $episode_id"

status=""
for i in {1..120}; do
  status=$(curl -fsS "http://localhost:8000/api/episode/$episode_id" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])')
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
card_count=$(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1])["cards"]))' "$query_json")
if [[ "$card_count" -lt 1 ]]; then
  FAIL "/api/query returned no cards"
fi
PASS "/api/query returned cards"

cit_ok=$(python3 -c 'import json,sys; payload=json.loads(sys.argv[1]); ok=any("start_ms" in cit and "end_ms" in cit for c in payload.get("cards", []) for cit in c.get("citations", [])); print("ok" if ok else "no")' "$query_json")
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
