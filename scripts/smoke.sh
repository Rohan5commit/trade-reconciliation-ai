#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
TRADE_DATE="${TRADE_DATE:-$(date -u +%Y-%m-%d)}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required" >&2
  exit 1
fi

pretty_print_json() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    python3 -m json.tool
  fi
}

wait_for_api() {
  local attempts=30
  local sleep_seconds=2
  local i

  for i in $(seq 1 "$attempts"); do
    if curl -fsS "${API_BASE_URL}/api/v1/health" >/dev/null; then
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "API did not become healthy at ${API_BASE_URL}" >&2
  return 1
}

echo "[1/6] Waiting for API health..."
wait_for_api

echo "[2/6] Health response"
curl -fsS "${API_BASE_URL}/api/v1/health" | pretty_print_json

echo "[3/6] Seeding demo data"
docker compose exec -T api python scripts/seed_demo_data.py

echo "[4/6] Running reconciliation for ${TRADE_DATE}"
curl -fsS -X POST "${API_BASE_URL}/api/v1/reconciliation/run" \
  -H "Content-Type: application/json" \
  -d "{\"trade_date\":\"${TRADE_DATE}T00:00:00\",\"source1\":\"oms\",\"source2\":\"custodian\"}" | pretty_print_json

echo "[5/6] Summary report"
curl -fsS "${API_BASE_URL}/api/v1/reports/summary" | pretty_print_json

echo "[6/6] Open breaks"
curl -fsS "${API_BASE_URL}/api/v1/breaks/open" | pretty_print_json

echo "Smoke flow complete."
