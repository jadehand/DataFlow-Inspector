#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

api_url="${DATAFLOW_API_URL:-http://127.0.0.1:18080}"

port="$(
  API_URL="$api_url" python3 -c \
    'import os, urllib.parse; parsed = urllib.parse.urlparse(os.environ["API_URL"]); print(parsed.port or (443 if parsed.scheme == "https" else 80))'
)"

if [[ "$port" == "8080" ]]; then
  echo "P2 check refuses to target port 8080." >&2
  exit 2
fi

make check
python3 tests_e2e/full_acceptance_test.py
