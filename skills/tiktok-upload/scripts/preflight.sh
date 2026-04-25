#!/usr/bin/env bash
# preflight.sh [project-dir]
# Verify all five prereqs before any TikTok upload.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${YT_CHROME_PORT:-9222}"
PROJECT="${1:-${TT_UPLOAD_PROJECT:-$PWD}}"

if ! command -v agent-browser >/dev/null 2>&1; then
  echo "FAIL: agent-browser not installed. Run: npm i -g agent-browser && agent-browser install" >&2
  echo "MISSING_AGENT_BROWSER" >&2; exit 10
fi

if ! curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
  echo "FAIL: Chrome not reachable on port ${PORT}. Run: ${SCRIPT_DIR}/chrome-launch.sh" >&2
  echo "CHROME_DOWN" >&2; exit 11
fi

"$SCRIPT_DIR/session-check.sh" >/dev/null 2>&1
case "$?" in
  0) ;;
  1) echo "FAIL: TikTok session expired. Sign in to tiktok.com in the Chrome window on port ${PORT}." >&2
     echo "SESSION_EXPIRED" >&2; exit 12 ;;
  2) echo "FAIL: Chrome stopped responding mid-check." >&2
     echo "CHROME_DOWN" >&2; exit 11 ;;
esac

# Cooldown — TikTok soft-blocks faster than IG, so honour cooldown aggressively.
COOLDOWN_FILE="$PROJECT/logs/tt-cooldown.until"
if [[ -f "$COOLDOWN_FILE" ]]; then
  until_ts="$(cat "$COOLDOWN_FILE" | tr -d '[:space:]')"
  now_ts="$(date -u +%s)"
  until_unix="$(date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$until_ts" +%s 2>/dev/null \
                || date -d "$until_ts" +%s 2>/dev/null || echo 0)"
  if (( until_unix > now_ts )); then
    echo "FAIL: cooldown active until ${until_ts} (TikTok soft-blocked the account)." >&2
    echo "COOLDOWN_ACTIVE" >&2; exit 14
  else
    rm "$COOLDOWN_FILE" 2>/dev/null
  fi
fi

DEFAULTS_CANDIDATES=(
  "$PROJECT/upload-defaults.yaml"
  "$PWD/upload-defaults.yaml"
  "$HOME/codeplay/ijp_research/CSOS/socials/tiktok-uploads/upload-defaults.yaml"
)
DEFAULTS=""
for cand in "${DEFAULTS_CANDIDATES[@]}"; do
  [[ -f "$cand" ]] && { DEFAULTS="$cand"; break; }
done
if [[ -z "$DEFAULTS" ]]; then
  echo "FAIL: no upload-defaults.yaml. Copy ${SCRIPT_DIR}/../assets/upload-defaults.template.yaml to your project." >&2
  echo "MISSING_DEFAULTS" >&2; exit 13
fi

echo "OK: agent-browser, Chrome:${PORT}, TikTok session, no cooldown, defaults=${DEFAULTS}"
exit 0
