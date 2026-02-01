#!/usr/bin/env bash
set -euo pipefail

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1"; exit 1; }

SR_URL="http://localhost:8081"

proto_tmp=$(mktemp)
cat > "$proto_tmp" <<'PROTO'
syntax = "proto3";
package iex.steps.v1;

message StepRequested {
  string episode_id = 1;
  string step = 2;
  string youtube_url = 3;
  int64 requested_at_ms = 4;
}

message StepCompleted {
  string episode_id = 1;
  string step = 2;
  string status = 3;
  string message = 4;
  int64 completed_at_ms = 5;
}
PROTO

export PROTO_PATH="$proto_tmp"
json_payload=$(python3 - <<'PY'
import json, os, pathlib
proto = pathlib.Path(os.environ["PROTO_PATH"]).read_text()
print(json.dumps({"schemaType":"PROTOBUF","schema": proto}))
PY
)

curl -fsS -X PUT -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data '{"compatibility":"BACKWARD"}' \
  "$SR_URL/config" > /dev/null \
  || FAIL "set global compatibility"
PASS "schema registry compatibility set to BACKWARD"

curl -fsS -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data "$json_payload" \
  "$SR_URL/subjects/events.steps.requested.v1-value/versions" > /dev/null \
  || FAIL "register StepRequested schema"
PASS "schema registered for events.steps.requested.v1-value"

curl -fsS -X POST -H "Content-Type: application/vnd.schemaregistry.v1+json" \
  --data "$json_payload" \
  "$SR_URL/subjects/events.steps.completed.v1-value/versions" > /dev/null \
  || FAIL "register StepCompleted schema"
PASS "schema registered for events.steps.completed.v1-value"

rm -f "$proto_tmp"
