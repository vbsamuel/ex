#!/usr/bin/env bash
set -euo pipefail

PASS() { echo "PASS: $1"; }
FAIL() { echo "FAIL: $1"; exit 1; }

MINIO_ENDPOINT="http://localhost:9000"
MINIO_USER="minio"
MINIO_PASS="minio123"
BUCKET="mini-brain"

if ! docker run --rm --network host minio/mc:RELEASE.2024-12-18T13-15-44Z \
  alias set iex "$MINIO_ENDPOINT" "$MINIO_USER" "$MINIO_PASS" > /dev/null; then
  FAIL "configure minio alias"
fi

if ! docker run --rm --network host minio/mc:RELEASE.2024-12-18T13-15-44Z \
  mb --ignore-existing iex/"$BUCKET" > /dev/null; then
  FAIL "create bucket $BUCKET"
fi

PASS "minio bucket $BUCKET ready"
