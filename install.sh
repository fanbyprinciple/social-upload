#!/usr/bin/env bash
# install.sh — install the youtube-upload, instagram-upload, and tiktok-upload
# skills into ~/.claude/skills/. Idempotent: re-running overwrites the installed
# copies with the latest from this repo.
#
# Usage:
#   ./install.sh                   # install all 3
#   ./install.sh youtube-upload    # install one
#   ./install.sh --uninstall       # remove all 3 from ~/.claude/skills/
#
# After install, the skills auto-trigger in any Claude Code session — Claude
# will see them in the available-skills list.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/.claude/skills"
ALL_SKILLS=(youtube-upload instagram-upload tiktok-upload)

if [[ "${1:-}" == "--uninstall" ]]; then
  for s in "${ALL_SKILLS[@]}"; do
    if [[ -d "$TARGET_DIR/$s" ]]; then
      echo "removing $TARGET_DIR/$s"
      rm -rf "$TARGET_DIR/$s"
    fi
  done
  echo "done"
  exit 0
fi

mkdir -p "$TARGET_DIR"

if [[ $# -eq 0 ]]; then
  SKILLS=("${ALL_SKILLS[@]}")
else
  SKILLS=("$@")
fi

for skill in "${SKILLS[@]}"; do
  src="$REPO_DIR/skills/$skill"
  dst="$TARGET_DIR/$skill"
  if [[ ! -d "$src" ]]; then
    echo "ERROR: unknown skill '$skill'. Choose from: ${ALL_SKILLS[*]}" >&2
    exit 1
  fi

  echo "[install] $skill → $dst"
  rm -rf "$dst"
  cp -R "$src" "$dst"

  # Drop the shared scripts in alongside the skill's own scripts. Each skill
  # references chrome-launch.sh and notify-email.sh from its own scripts/ dir,
  # so we copy them in (rather than symlink — symlinks break on Windows clones
  # and on Cowork environments).
  cp "$REPO_DIR/shared/chrome-launch.sh" "$dst/scripts/"
  cp "$REPO_DIR/shared/notify-email.sh"  "$dst/scripts/"
  chmod +x "$dst/scripts/"*.sh "$dst/scripts/"*.py 2>/dev/null || true
done

cat <<EOF

Installed: ${SKILLS[*]}

Next steps:
  1. Pick a project dir for each platform you want to use, e.g.
       ~/codeplay/ijp_research/CSOS/socials/youtube-upload/
       ~/codeplay/ijp_research/CSOS/socials/instagram-reels/
       ~/codeplay/ijp_research/CSOS/socials/tiktok-uploads/
  2. Copy the matching sample from $REPO_DIR/projects-sample/<name>/
     into your project dir, then edit upload-defaults.yaml.
  3. Run the launcher: $REPO_DIR/shared/chrome-launch.sh
     and sign in to YouTube Studio / Instagram / TikTok in the Opera/Chrome
     window that opens.
  4. Drop a .mp4 into <project>/videos/ and run:
       ~/.claude/skills/<skill>/scripts/upload-queue.sh <project-dir>

  Or just open a Claude Code session and say "upload to youtube" — the skill
  triggers automatically.
EOF
