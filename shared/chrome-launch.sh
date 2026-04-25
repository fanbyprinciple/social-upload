#!/usr/bin/env bash
# chrome-launch.sh — open a real Chrome with the CDP debug port + a persistent
# profile. The user signs in to YouTube Studio in this window once; the profile
# remembers cookies across reboots.
#
# IMPORTANT: this Chrome window must stay running for the skill to upload.
# Closing it kills the CDP port. Re-launching with the same profile resumes
# the same session.

set -euo pipefail

PORT="${YT_CHROME_PORT:-9222}"
PROFILE="${YT_CHROME_PROFILE:-$HOME/.youtube-upload-chrome-profile}"

if curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
  echo "[chrome-launch] Chrome already on port ${PORT} — no relaunch needed."
  exit 0
fi

# Browser preference order. Override with $YT_BROWSER=opera|chrome|chromium|brave|edge.
BROWSER_PREF="${YT_BROWSER:-}"
case "$(uname -s)" in
  Darwin)
    declare -a CANDIDATES=(
      "/Applications/Opera.app/Contents/MacOS/Opera"
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
      "/Applications/Chromium.app/Contents/MacOS/Chromium"
      "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
      "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
    )
    ;;
  Linux)
    declare -a CANDIDATES=(
      "$(command -v opera || true)"
      "$(command -v google-chrome || true)"
      "$(command -v chromium || true)"
      "$(command -v brave-browser || true)"
      "$(command -v microsoft-edge || true)"
    )
    ;;
  *) echo "unsupported OS: $(uname -s)" >&2; exit 1 ;;
esac

# If user named a specific browser, pick that path.
pref_lc="$(echo "$BROWSER_PREF" | tr '[:upper:]' '[:lower:]')"
if [[ -n "$pref_lc" ]]; then
  for c in "${CANDIDATES[@]}"; do
    c_lc="$(echo "$c" | tr '[:upper:]' '[:lower:]')"
    [[ -x "$c" ]] && [[ "$c_lc" == *"$pref_lc"* ]] && BROWSER="$c" && break
  done
else
  for c in "${CANDIDATES[@]}"; do
    [[ -n "$c" && -x "$c" ]] && BROWSER="$c" && break
  done
fi

if [[ -z "${BROWSER:-}" || ! -x "$BROWSER" ]]; then
  echo "no Chromium-family browser found (Opera/Chrome/Chromium/Brave/Edge)" >&2; exit 1
fi

mkdir -p "$PROFILE"
echo "[chrome-launch] starting $(basename "$BROWSER") on port ${PORT} with profile ${PROFILE}"
echo "[chrome-launch] sign in to YouTube Studio in the window that opens, then leave it running."

nohup "$BROWSER" \
  --remote-debugging-port="$PORT" \
  --user-data-dir="$PROFILE" \
  >/dev/null 2>&1 &

# Wait briefly for port to come up.
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 1
  if curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
    echo "[chrome-launch] Chrome is up on port ${PORT}."
    exit 0
  fi
done

echo "[chrome-launch] Chrome did not respond on port ${PORT} within 10s" >&2
exit 1
