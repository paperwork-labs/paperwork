#!/usr/bin/env bash
# verify.sh — smoke-test an AxiomFolio API base URL.
# Usage: verify.sh https://api.axiomfolio.com
#        verify.sh https://axiomfolio-api-xxxx.onrender.com

set -euo pipefail

BASE="${1:?Usage: $0 <api-base-url>}"
BASE="${BASE%/}"

echo ">> Verifying $BASE"

echo -n "   GET /health ... "
code=$(curl -s -o /tmp/af-verify.body -w "%{http_code}" "$BASE/health")
if [[ "$code" == "200" ]]; then
  echo "200 OK"
else
  echo "FAIL ($code): $(cat /tmp/af-verify.body | head -c 200)"
  exit 1
fi

echo -n "   GET /api/v1/health (detailed) ... "
code=$(curl -s -o /tmp/af-verify.body -w "%{http_code}" "$BASE/api/v1/health" || true)
if [[ "$code" == "200" || "$code" == "404" ]]; then
  echo "$code ($(jq -r '.status // "no_status"' /tmp/af-verify.body 2>/dev/null || echo "-"))"
else
  echo "$code"
fi

echo -n "   TLS cert check ... "
if curl -sI "$BASE" -o /dev/null; then
  echo "OK"
else
  echo "FAIL"
  exit 1
fi

echo -n "   Response time (5 samples) ... "
for i in 1 2 3 4 5; do
  curl -s -o /dev/null -w "%{time_total}s " "$BASE/health"
done
echo ""

echo ">> $BASE looks healthy"
