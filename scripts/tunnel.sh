#!/usr/bin/env bash
# Give the hub a public address so Africa's Talking can deliver the host's replies.
#
# Outgoing SMS needs nothing but the API key. Incoming SMS is a webhook, so the
# operator has to be able to reach this machine. This opens a Cloudflare quick
# tunnel, which needs no account and no token, and prints the URL to paste into
# the sandbox callback setting.
#
#     ./scripts/tunnel.sh          # tunnels port 8000
#     ./scripts/tunnel.sh 9000     # or another port
#
# The address is temporary: it changes every time this script runs, so update
# the callback setting whenever you restart it.
set -euo pipefail

PORT="${1:-8000}"
LOG="$(mktemp -t karibu-tunnel.XXXXXX)"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed. Either install it, or use another tunnel"
  echo "and point it at http://localhost:$PORT."
  exit 1
fi

if ! curl -fsS -m 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "Nothing is answering on port $PORT. Start the hub first:"
  echo "    uvicorn hub.app:app --port $PORT"
  exit 1
fi

echo "opening a public address for port $PORT ..."
cloudflared tunnel --url "http://localhost:$PORT" --no-autoupdate >"$LOG" 2>&1 &
TUNNEL_PID=$!
trap 'kill "$TUNNEL_PID" 2>/dev/null || true' EXIT INT TERM

URL=""
for _ in $(seq 1 40); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done

if [ -z "$URL" ]; then
  echo "the tunnel did not come up. Last few lines:"
  tail -20 "$LOG"
  exit 1
fi

if curl -fsS -m 20 "$URL/health" >/dev/null 2>&1; then
  echo "the hub answers on the public address"
else
  echo "warning: the public address did not answer /health yet, give it a moment"
fi

cat <<EOF

  Paste this as the SMS callback in the Africa's Talking sandbox:

      $URL/api/sms/inbound

  Sandbox app, then SMS, then Callback URLs, then the inbox or incoming-messages
  callback. Leave this running while you demo; closing it closes the tunnel.

EOF

wait "$TUNNEL_PID"
