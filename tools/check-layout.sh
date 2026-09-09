#!/usr/bin/env bash
# Run the layout guard against a throwaway static server.
#
# check-layout.js needs the site over HTTP rather than from disk: the pages
# load their assets by relative path, and a file:// origin resolves those
# differently than a served one, so measuring a file:// page would measure a
# layout no visitor ever gets.
set -euo pipefail

PORT="${PORT:-8899}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"

# A server already on the port would be silently measured instead of this
# checkout — which is how a stale tree passes a check it should have failed.
if curl -fsS -o /dev/null "http://127.0.0.1:${PORT}/" 2>/dev/null; then
  echo "port ${PORT} is already serving something; stop it or set PORT=" >&2
  exit 1
fi

python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  if curl -fs -o /dev/null "http://127.0.0.1:${PORT}/"; then break; fi
  sleep 0.25
done

node tools/check-layout.js "http://127.0.0.1:${PORT}"
