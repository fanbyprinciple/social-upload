#!/usr/bin/env bash
# preflight.sh [project-dir]
# Verifies all four prereqs before any upload. Exits 0 if everything's ready,
# non-zero with a clear message otherwise. Stdout is human-readable; stderr is
# machine-parseable codes for the queue runner.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${YT_CHROME_PORT:-9222}"
PROJECT="${1:-${YT_UPLOAD_PROJECT:-$PWD}}"

# 1. agent-browser on PATH
if ! command -v agent-browser >/dev/null 2>&1; then
  echo "FAIL: agent-browser not installed. Run: npm i -g agent-browser && agent-browser install" >&2
  echo "MISSING_AGENT_BROWSER" >&2
  exit 10
fi

# 2. Chrome reachable on debug port
if ! curl -s "http://localhost:${PORT}/json/version" >/dev/null 2>&1; then
  echo "FAIL: Chrome not reachable on port ${PORT}. Run: ${SCRIPT_DIR}/chrome-launch.sh" >&2
  echo "CHROME_DOWN" >&2
  exit 11
fi

# 3. Studio session valid
"$SCRIPT_DIR/session-check.sh" >/dev/null 2>&1
case "$?" in
  0) ;;
  1)
    echo "FAIL: YouTube session expired. Sign in to studio.youtube.com in the Chrome window on port ${PORT}." >&2
    echo "SESSION_EXPIRED" >&2
    exit 12
    ;;
  2)
    echo "FAIL: Chrome stopped responding mid-check." >&2
    echo "CHROME_DOWN" >&2
    exit 11
    ;;
esac

# 4. Defaults YAML reachable
DEFAULTS_CANDIDATES=(
  "$PROJECT/upload-defaults.yaml"
  "$PWD/upload-defaults.yaml"
  "$HOME/codeplay/ijp_research/CSOS/socials/youtube-upload/upload-defaults.yaml"
)
DEFAULTS=""
for cand in "${DEFAULTS_CANDIDATES[@]}"; do
  if [[ -f "$cand" ]]; then DEFAULTS="$cand"; break; fi
done
if [[ -z "$DEFAULTS" ]]; then
  echo "FAIL: no upload-defaults.yaml found. Copy from ${SCRIPT_DIR}/../assets/upload-defaults.template.yaml to your project." >&2
  echo "MISSING_DEFAULTS" >&2
  exit 13
fi

echo "OK: agent-browser, Chrome:${PORT}, Studio session, defaults=${DEFAULTS}"
exit 0
