#!/usr/bin/env bash
# notify-email.sh <subject> <body> [recipient]
# Sends a plain-text email via macOS `mail` (assumes msmtp/Postfix is set up,
# or falls back to printing to stderr). Used for session-expired alerts.
#
# Recipient resolution: explicit arg → $YT_NOTIFY_EMAIL → upload-defaults.yaml
# `notify_email` key (resolved by the caller, passed in here).

set -euo pipefail

subject="${1:?usage: notify-email.sh <subject> <body> [recipient]}"
body="${2:-}"
to="${3:-${YT_NOTIFY_EMAIL:-}}"

if [[ -z "$to" ]]; then
  echo "[notify-email] no recipient — skipping email. Subject was: $subject" >&2
  exit 0
fi

if command -v mail >/dev/null 2>&1; then
  printf '%s\n' "$body" | mail -s "$subject" "$to" \
    && echo "[notify-email] sent to $to" \
    || echo "[notify-email] mail command failed — make sure msmtp/Postfix is configured" >&2
else
  echo "[notify-email] mail command not found. Install msmtp + create ~/.msmtprc, or set up Postfix." >&2
fi

# Always also fire a macOS banner so the alert is visible even if mail fails.
if command -v osascript >/dev/null 2>&1; then
  osascript -e "display notification \"$body\" with title \"$subject\"" >/dev/null 2>&1 || true
fi
