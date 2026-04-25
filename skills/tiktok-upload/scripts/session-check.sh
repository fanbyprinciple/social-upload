#!/usr/bin/env bash
# session-check.sh — exits 0 if a TikTok session cookie is present in Chrome,
# 1 if no TikTok cookie / cookie expired, 2 if Chrome itself is unreachable.
#
# Passive cookie probe — does NOT navigate to tiktok.com. TikTok's anti-spam
# is the strictest of the three platforms; every browser-driven navigation
# burns goodwill against the account. Trust the cookie; let the actual upload
# run surface a real failure if the cookie is dead.

set -euo pipefail

PORT="${YT_CHROME_PORT:-9222}"

if ! curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
  echo "[tt session-check] Chrome not reachable on port ${PORT}" >&2
  exit 2
fi

# TikTok session: `sessionid` cookie + `tt_csrf_token` (web auth pair).
# Both must be present.
sessionid_present="$(agent-browser --auto-connect cookies get 2>/dev/null | grep -cE "^sessionid=" || true)"
csrf_present="$(agent-browser --auto-connect cookies get 2>/dev/null | grep -cE "^tt_csrf_token=" || true)"

if [[ "$sessionid_present" -ge 1 && "$csrf_present" -ge 1 ]]; then
  echo "[tt session-check] sessionid + tt_csrf_token present — TikTok session likely valid"
  exit 0
fi

echo "[tt session-check] missing TikTok cookies (sessionid=$sessionid_present, csrf=$csrf_present) — sign in to tiktok.com in the Chrome window on port ${PORT}" >&2
exit 1
