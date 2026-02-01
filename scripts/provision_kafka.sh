#!/usr/bin/env bash
set -euo pipefail

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1"; exit 1; }

BOOTSTRAP="localhost:9092"
KAFKA_EXEC=(docker compose exec -T kafka)

ensure_topic() {
  local name="$1"
  local partitions="$2"
  local retention_ms="$3"
  local cleanup_policy="$4"

  if ! "${KAFKA_EXEC[@]}" kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list | grep -q "^${name}$"; then
    "${KAFKA_EXEC[@]}" kafka-topics.sh --bootstrap-server "$BOOTSTRAP" \
      --create --if-not-exists --topic "$name" \
      --partitions "$partitions" --replication-factor 1 \
      --config retention.ms="$retention_ms" --config cleanup.policy="$cleanup_policy" \
      || FAIL "create topic $name"
  fi

  local describe_out
  if ! describe_out=$("${KAFKA_EXEC[@]}" kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --describe --topic "$name"); then
    FAIL "describe topic $name"
  fi

  local current_partitions
  current_partitions=$(awk -F'PartitionCount:' 'NF>1{p=$2; sub(/^[[:space:]]*/,"",p); sub(/[[:space:]].*/,"",p); print p; exit}' <<<"$describe_out")

  if [[ -z "${current_partitions:-}" ]]; then
    FAIL "read partitions for $name"
  fi

  if (( current_partitions < partitions )); then
    "${KAFKA_EXEC[@]}" kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --alter --topic "$name" --partitions "$partitions" \
      || FAIL "increase partitions for $name"
  fi

  "${KAFKA_EXEC[@]}" kafka-configs.sh --bootstrap-server "$BOOTSTRAP" \
    --entity-type topics --entity-name "$name" \
    --alter --add-config "retention.ms=${retention_ms},cleanup.policy=${cleanup_policy}" \
    || FAIL "set configs for $name"

  PASS "topic $name configured"
}

ensure_topic "events.orchestrator.v1" 12 2592000000 delete
ensure_topic "events.steps.requested.v1" 24 2592000000 delete
ensure_topic "events.steps.completed.v1" 24 2592000000 delete
ensure_topic "events.kb.v1" 12 7776000000 delete
ensure_topic "events.interaction.v1" 12 2592000000 delete
ensure_topic "events.metrics.v1" 12 15552000000 delete
ensure_topic "events.dlq.v1" 12 15552000000 delete
