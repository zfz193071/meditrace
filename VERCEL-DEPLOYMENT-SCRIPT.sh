#!/usr/bin/env bash
# Backward-compatible entry point; keep deployment logic in one file.
set -euo pipefail
DEPLOY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec "$DEPLOY_ROOT/deploy-vercel.sh" "$@"
