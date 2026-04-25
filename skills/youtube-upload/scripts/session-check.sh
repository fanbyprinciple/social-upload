#!/usr/bin/env bash
# session-check.sh — exits 0 if a Google session cookie is present in Chrome,
# 1 if no Google cookie / cookie expired, 2 if Chrome itself is unreachable.
#
# DESIGN NOTE: Earlier versions navigated to studio.youtube.com to probe
# sign-in state. That worked but burned a real Studio page-load every preflight
# call (cost: a few HTTP requests + risk of triggering Google's automation
# heuristics under heavy load). This version checks the cookie jar passively
# via Chrome DevTools Protocol — no navigation, no Google server contact.
# An invalid cookie still surfaces as a real failure on the actual upload run.

set -euo pipefail

PORT="${YT_CHROME_PORT:-9222}"

if ! curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
  echo "[session-check] Chrome not reachable on port ${PORT}" >&2
  exit 2
fi

# Google's session cookies — at least one of SAPISID / SID / HSID must be set
# for studio.youtube.com to consider the user signed in.
google_cookie_count="$(agent-browser --auto-connect cookies get 2>/dev/null \
  | grep -cE "^[^=]*\b(SAPISID|SID|HSID|__Secure-1PSID)\b" || true)"

if [[ "$google_cookie_count" -ge 1 ]]; then
  echo "[session-check] Google session cookie present — Studio session likely valid"
  exit 0
fi

echo "[session-check] no Google session cookie found — sign in to studio.youtube.com in the Chrome window on port ${PORT}" >&2
exit 1
