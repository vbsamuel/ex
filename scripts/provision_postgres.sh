#!/usr/bin/env bash
set -euo pipefail

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1"; exit 1; }

COMPOSE=(docker compose -f docker-compose.demo.yml)

"${COMPOSE[@]}" exec -T postgres psql -U mini_brain -d mini_brain -v ON_ERROR_STOP=1 -f /migrations/001_init.sql \
  || FAIL "apply migrations"
PASS "postgres migrations applied"
