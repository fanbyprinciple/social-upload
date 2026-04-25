#!/usr/bin/env bash
# upload-queue.sh [project-dir]
# Iterate the videos/ folder, upload one TikTok video at a time, respect daily
# cap + cooldown, move failed files to videos/failed/, email on session expiry
# or soft-block.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="${1:-${TT_UPLOAD_PROJECT:-$HOME/codeplay/ijp_research/CSOS/socials/tiktok-uploads}}"
VIDEOS="$PROJECT/videos"
FAILED="$VIDEOS/failed"
LOGS="$PROJECT/logs"
LOG="$LOGS/upload.log"
POSTED_LOG="$VIDEOS/posted.log"
COOLDOWN_FILE="$LOGS/tt-cooldown.until"

mkdir -p "$FAILED" "$LOGS"

_log() { printf '[%s] %s\n' "$(date -Iseconds)" "$*" | tee -a "$LOG"; }

read_yaml() {
  local key="$1" default="$2"
  python3 - "$PROJECT/upload-defaults.yaml" "$key" "$default" <<'PY'
import sys, yaml
p, key, default = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    cfg = yaml.safe_load(open(p)) or {}
    print(cfg.get(key, default))
except FileNotFoundError:
    print(default)
PY
}

DAILY_CAP="$(read_yaml daily_cap 10)"
PACE="$(read_yaml pace_seconds 600)"
NOTIFY_EMAIL="$(read_yaml notify_email '')"
export YT_NOTIFY_EMAIL="$NOTIFY_EMAIL"

# Rotate log if >10MB.
if [[ -f "$LOG" ]]; then
  size=$(stat -f%z "$LOG" 2>/dev/null || stat -c%s "$LOG" 2>/dev/null || echo 0)
  if (( size > 10485760 )); then
    mv "$LOG" "$LOG.$(date +%Y%m%d-%H%M%S)"
    _log "queue: rotated log"
  fi
fi

if ! "$SCRIPT_DIR/preflight.sh" "$PROJECT" 2>>"$LOG"; then
  rc=$?
  _log "queue: preflight failed (rc=$rc)"
  case "$rc" in
    12) "$SCRIPT_DIR/notify-email.sh" "TikTok session expired" \
          "Sign back in to tiktok.com in the Chrome window on port 9222. Queue resumes on next fire." \
          "$NOTIFY_EMAIL" ;;
    14) "$SCRIPT_DIR/notify-email.sh" "TikTok cooldown active" \
          "TikTok soft-blocked the account. Queue paused until $(cat "$COOLDOWN_FILE" 2>/dev/null)." \
          "$NOTIFY_EMAIL" ;;
  esac
  exit "$rc"
fi

today="$(date +%Y-%m-%d)"
todays_count=0
if [[ -f "$POSTED_LOG" ]]; then
  todays_count=$(grep -c "^${today}" "$POSTED_LOG" || true)
fi
if (( todays_count >= DAILY_CAP )); then
  _log "queue: daily cap ${DAILY_CAP} reached (${todays_count} today). Resting until tomorrow."
  exit 0
fi

remaining=$(( DAILY_CAP - todays_count ))
shopt -s nullglob
videos=("$VIDEOS"/*.mp4 "$VIDEOS"/*.mov "$VIDEOS"/*.m4v "$VIDEOS"/*.webm)
if (( ${#videos[@]} == 0 )); then
  _log "queue: no videos in $VIDEOS"
  exit 0
fi
IFS=$'\n' videos=($(stat -f '%m %N' "${videos[@]}" 2>/dev/null | sort -n | cut -d' ' -f2-))
unset IFS

uploaded=0 failed=0
for video in "${videos[@]}"; do
  (( uploaded >= remaining )) && { _log "queue: hit daily cap mid-loop, stopping"; break; }

  base=$(basename "$video")
  _log "queue: starting $base"

  if url=$(python3 "$SCRIPT_DIR/upload-one.py" "$video" 2>>"$LOG"); then
    _log "queue: OK $base -> $url"
    uploaded=$((uploaded + 1))
  else
    rc=$?
    _log "queue: FAIL $base (rc=$rc)"
    case "$rc" in
      75)
        "$SCRIPT_DIR/notify-email.sh" "TikTok session expired mid-queue" \
          "Sign back in to tiktok.com. Queue paused after ${uploaded} successful uploads today." \
          "$NOTIFY_EMAIL"
        exit 75
        ;;
      77)
        _log "queue: TikTok soft-blocked; setting 24h cooldown"
        until_ts="$(date -u -v+24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
                    || date -u -d '+24 hours' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null)"
        echo "$until_ts" > "$COOLDOWN_FILE"
        "$SCRIPT_DIR/notify-email.sh" "TikTok soft-block — 24h cooldown" \
          "TikTok showed soft-block message. Queue paused until ${until_ts}." \
          "$NOTIFY_EMAIL"
        exit 0
        ;;
      *)
        mv "$video" "$FAILED/" 2>/dev/null || true
        echo "rc=$rc on $(date -Iseconds)" > "$FAILED/${base}.error"
        for ext in yaml jpg png; do
          src="${video%.*}.$ext"
          [[ -f "$src" ]] && mv "$src" "$FAILED/" 2>/dev/null || true
        done
        failed=$((failed + 1))
        ;;
    esac
  fi

  last_idx=$(( ${#videos[@]} - 1 ))
  if (( uploaded < remaining )) && [[ "$video" != "${videos[$last_idx]}" ]]; then
    sleep "$PACE"
  fi
done

_log "queue: done — uploaded=${uploaded} failed=${failed}"
exit 0
