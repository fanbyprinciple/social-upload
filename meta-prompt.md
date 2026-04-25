# meta-prompt.md — install instructions for a Claude agent

You (the Claude agent reading this) have been pointed at this `social-upload`
repo. The user wants you to install the bundle and bring up at least one of
the three skills (`youtube-upload`, `instagram-upload`, `tiktok-upload`) so
they can start posting.

## Order of operations

1. **Confirm prerequisites.** Run these checks; if any fails, stop and tell
   the user the exact fix:
   - `command -v agent-browser` — install via `npm i -g agent-browser && agent-browser install` if missing
   - `python3 -c "import yaml"` — install via `pip install --break-system-packages pyyaml` if missing
   - `command -v gh` — only needed if user wants to fork/PR back to this repo

2. **Install the skills.** From the repo root:
   ```bash
   ./install.sh
   ```
   This copies each skill into `~/.claude/skills/<name>/` and inlines the
   shared scripts. Idempotent — safe to re-run.

3. **Ask the user which platform(s) they want to start with.** Don't try to
   set up all three blindly — each one needs:
   - A signed-in browser session (manual)
   - A project folder with `upload-defaults.yaml` filled in
   - Videos dropped into `videos/`
   Keep it incremental. One platform working end-to-end > three half-installed.

4. **For each platform the user picks**, do the following:

   a. **Create the project folder** by copying the matching sample:
      ```bash
      cp -R projects-sample/<name>/ ~/codeplay/<wherever-the-user-wants>/<name>/
      ```
      Sample names map directly: `youtube-upload`, `instagram-reels`,
      `tiktok-uploads`. The user can name the destination folder whatever
      they want.

   b. **Open the user's `upload-defaults.yaml`** in that project folder.
      Walk them through the fields that matter for their use case. Don't
      dump the whole schema — surface the 3–5 fields they're likely to
      change (`caption` / `visibility` / `daily_cap` / `notify_email`).

   c. **Bring up the browser session.** Run:
      ```bash
      ~/.claude/skills/<skill-name>/scripts/chrome-launch.sh
      ```
      Tell the user: "An Opera/Chrome window just opened. Sign in to
      `<platform>` in that window. Tell me when done."

   d. **Verify with preflight.** Once they confirm, run:
      ```bash
      ~/.claude/skills/<skill-name>/scripts/preflight.sh <project-dir>
      ```
      Should print `OK: ...`. Surface any FAIL plainly.

   e. **First upload.** Ask the user to drop one `.mp4` into
      `<project-dir>/videos/`. Then run:
      ```bash
      ~/.claude/skills/<skill-name>/scripts/upload-queue.sh <project-dir>
      ```
      Watch the log; report the URL on success.

5. **Offer recurring scheduling.** After a successful first upload, point at
   `skills/<name>/references/launchd.plist`. Adapt paths for the user's home
   dir, install via `launchctl bootstrap`, and confirm with `launchctl list`.

## Platform-specific things to know before walking the user through

### youtube-upload
- Works on any YouTube account.
- Required YAML fields: `made_for_kids`, `altered_content`, `visibility`.
  Studio refuses to publish if these aren't set.
- Title / description / tags auto-derived from filename if blank.
- Vertical 9:16 videos auto-classified as Shorts; URL pattern is
  `https://youtube.com/shorts/<id>` rather than `youtu.be/<id>`. The skill
  handles both.

### instagram-upload
- **Account must be Creator or Business.** Personal accounts fail with
  "Only images can be posted." Skill detects this (exit 78) and tells the
  user to convert via Settings → Account type → Switch to Professional.
- Critical CSS selector: `input[type=file][accept*="video"]`. IG renders
  three file inputs on the page; only the third accepts video. Generic
  `input[type=file]` fails silently.
- Music picker is **not exposed** on IG web for newly-converted Creator
  accounts. The YAML `music_search` / `music_track_url` fields are inert
  until IG enables the music library on the acct (days–weeks).

### tiktok-upload
- Two backends: `api` (preferred when configured) and `browser` (fallback).
  Default `mode: auto` tries API first.
- API needs `tiktok-api-creds.yaml` filled in (template at
  `assets/tiktok-api-creds.yaml.example`). User must run TikTok's OAuth
  flow once to capture `access_token` + `refresh_token`. **You can't do
  this for them — it requires interactive authorization.**
- TikTok anti-spam fires fastest of the three. Defaults are 5/day, 1 hr
  pace. Don't raise without explicit user pushback.
- Browser-mode selectors are best-guess; live verification needed on first
  run. Capture a screenshot if upload-one.py exits 71.

## Hard things to NOT do (learned from prior runs)

- **Don't navigate to platform sites in `session-check.sh`.** Use the cookie
  probe pattern. Repeated session-probe navigations contributed to a real
  Instagram account soft-block during development.
- **Don't retry sign-in attempts in a loop.** One try, then bail and tell
  the user. Each retry deepens the platform's automation flag.
- **Don't symlink shared scripts in the installed skills.** `install.sh`
  copies them in. Symlinks break on Windows clones and Cowork environments.
- **Don't commit `tiktok-api-creds.yaml`, `videos/posted.log` with real URLs,
  `logs/*`, or `videos/*.mp4`.** The repo `.gitignore` covers the project
  folders the user creates outside the repo, but if they create a project
  folder INSIDE the repo, double-check.

## What success looks like

The user can:
1. Drop a `.mp4` into `<project>/videos/`
2. Wait for the launchd cron to fire (or run `upload-queue.sh` manually)
3. See the URL appear in `<project>/videos/posted.log`
4. Get an email if anything goes wrong

If they're not at that point yet, they're not done. Keep iterating.
