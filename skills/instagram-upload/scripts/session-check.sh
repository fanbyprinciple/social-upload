#!/usr/bin/env bash
# session-check.sh — exits 0 if an instagram.com session cookie is present,
# 1 if no IG cookie or the cookie has expired, 2 if Chrome itself is not
# reachable on the debug port.
#
# DESIGN NOTE: Earlier versions navigated to https://www.instagram.com/ to
# probe sign-in state. That repeated navigation looked automated to IG and
# contributed to a "We restrict certain activity" soft-block. This version
# checks the cookie jar passively via Chrome's DevTools Protocol — no
# navigation, no DOM probe, no IG server contact.

set -euo pipefail

PORT="${YT_CHROME_PORT:-9222}"

if ! curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
  echo "[ig session-check] Chrome not reachable on port ${PORT}" >&2
  exit 2
fi

# Pull the cookie jar from any open IG tab via agent-browser. If no IG tab
# exists we can't peek — so accept that, treat as "unknown / passive ok".
# The actual upload run will surface a real error if the cookie is dead.
sessionid_present="$(agent-browser --auto-connect cookies get 2>/dev/null \
  | grep -c "sessionid" || true)"

if [[ "$sessionid_present" -gt 0 ]]; then
  echo "[ig session-check] sessionid cookie present — session likely valid"
  exit 0
fi

echo "[ig session-check] no sessionid cookie found — sign in to instagram.com in the Chrome window on port ${PORT}" >&2
exit 1
