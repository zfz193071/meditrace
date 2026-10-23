#!/usr/bin/env bash
# Read-only local smoke checks. No model, payment or packet writes.
set -euo pipefail
BASE_URL="${BASE_URL:-http://localhost:8000}"
curl --fail --silent --show-error "$BASE_URL/api/v1/capabilities"
readiness="$(curl --silent --show-error --output /dev/null --write-out '%{http_code}' "$BASE_URL/api/v1/readiness")"
test "$readiness" = "200" || test "$readiness" = "503"
status="$(curl --silent --output /dev/null --write-out '%{http_code}' "$BASE_URL/api/conversations")"
test "$status" = "410"
