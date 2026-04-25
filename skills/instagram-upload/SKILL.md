---
name: instagram-upload
description: Upload Reels to Instagram — one or many — by driving instagram.com's web Reel composer through agent-browser attached to a real, signed-in Chrome/Opera. Use this skill whenever the user wants to publish Reels to their Instagram account, queue Reels uploads from a folder, schedule a recurring Instagram uploader, set Reel metadata (caption, hashtags, location, collaborators, tagged people, topics, cover frame, paid partnership, crosspost to Facebook, hide likes/views, disable comments), recover from session expiry or anti-spam soft-blocks, or work with the instagram-reels app at CSOS/socials/instagram-reels. Strong triggers — "upload to instagram", "post reel", "upload reel", "instagram uploader", "auto upload reels", "post videos to instagram", "bulk upload instagram", "drop reels in folder and upload daily", "instagram reel from yaml", "schedule instagram upload", "upload to insta", "ig upload", "instagram shorts". Use proactively whenever the user references uploading any video file to an Instagram account, even if they don't name this skill. Note: this skill is for Reels (vertical 9:16, ≤90 sec). For YouTube use the youtube-upload skill.
---

# Instagram Reels upload (browser-driven)

Drives instagram.com's web Reel composer end-to-end via `agent-browser --auto-connect` against a Chrome/Opera window the user has signed into. Reads metadata from a YAML defaults file (with optional per-video sidecar), uploads the oldest pending video in a folder, shares as a Reel, deletes the source on success, logs the Reel URL.

Designed for single-account use, sustained over days, with conservative pacing because Instagram's anti-automation fires fast.

## Why driving real Chrome (and not the Graph API)

The user wants browser automation. Use it.

The Instagram Graph API requires a Business or Creator account linked to a Facebook Page, OAuth setup, and a content-publishing permission that takes app review. For a single hobby/creator account, the web composer is faster to set up — the cost is fragility and the constant risk of soft-blocks.

The skill MUST attach to a *real* browser via `agent-browser --auto-connect` on CDP port 9222 — same browser/window that the youtube-upload skill uses. Instagram detects automation aggressively in agent-browser's bundled Chromium; only a real, persistent profile that the user has signed into via the actual UI survives.

## Hard new risk vs YouTube — anti-spam

Instagram throttles aggressively. Defaults are conservative:

- **Daily cap = 25 Reels/day** (vs YouTube's 50)
- **Pace = 5 min minimum between Reels** (vs YouTube's 60 sec)
- On any "We limit how often you can do certain things" modal, the skill writes `logs/ig-cooldown.until=<iso8601>` and refuses to fire for 24 h.
- 2FA challenges are routine — every few days IG will require an SMS/authenticator code mid-session. Skill detects + halts + emails.

Repeated automation can lead to permanent account suspension. **Do not raise the cap or shorten the pace without thinking carefully**.

## Prerequisites checklist

Use `scripts/preflight.sh`. It checks:

1. `agent-browser` is installed and on PATH.
2. Chrome/Opera is alive at `http://localhost:9222/json/version`.
3. The session is signed into Instagram — `agent-browser --auto-connect open https://www.instagram.com/` lands on the home feed (not the login page).
4. No active cooldown — `logs/ig-cooldown.until` is absent or in the past.
5. A defaults YAML is reachable. Resolution order: `--config` arg → `$IG_UPLOAD_PROJECT/upload-defaults.yaml` → `$PWD/upload-defaults.yaml` → `$HOME/codeplay/ijp_research/CSOS/socials/instagram-reels/upload-defaults.yaml`.

If any check fails, surface it plainly and stop.

## One-time user setup

The browser launch script is the same one the YouTube skill uses (symlinked into this skill's `scripts/chrome-launch.sh`). One Chrome/Opera window serves both skills:

```bash
~/.claude/skills/instagram-upload/scripts/chrome-launch.sh
```

In that window, sign in to **both** instagram.com and studio.youtube.com. The profile dir (`~/.youtube-upload-chrome-profile`) persists cookies; you only re-auth when each site rotates its session (~1 month for IG, ~2 weeks for YouTube).

## File layout

```
<project>/                           # default: ~/codeplay/ijp_research/CSOS/socials/instagram-reels/
├── upload-defaults.yaml             # global defaults — applies to every Reel
├── videos/
│   ├── <name>.mp4                   # 9:16 vertical, ≤90 sec, ≤4 GB
│   ├── <name>.yaml                  # OPTIONAL — per-video metadata overlay
│   ├── <name>.jpg                   # OPTIONAL — custom cover image
│   ├── posted.log                   # filename + URL appended on success (NO video kept)
│   └── failed/<name>.{mp4,error}    # failure → file moved here + .error sidecar
└── logs/
    ├── upload.log                   # appended; rotated at 10 MB
    └── ig-cooldown.until            # presence = queue is paused; auto-removed after expiry
```

On success the source `.mp4` is **deleted** along with sidecar `.yaml`/`.jpg`, and the upload is recorded in `videos/posted.log` (`<iso-timestamp>\t<filename>\t<reel-url>`).

## upload-defaults.yaml — schema

Canonical commented version at `assets/upload-defaults.template.yaml`. Key fields:

| Section | Key | Values |
|---------|-----|--------|
| basic | `caption` | string ≤2200 chars; `#hashtags` and `@mentions` inline |
| basic | `location` | free-form string; IG autocompletes |
| basic | `collaborators` | list of `@handles` (max 3) |
| basic | `tagged_people` | list of `@handles` |
| basic | `topics` | list of ≤3 from IG's preset list |
| basic | `paid_partnership` | bool |
| privacy | `crosspost_to_facebook` | bool, default true |
| privacy | `hide_like_count` `hide_view_count` `disable_comments` | bool |
| privacy | `audience_close_friends` | bool (personal account only; ignored on creator) |
| cover | `cover_frame_seconds` | int — frame at N seconds in; null → IG picks |
| cover | `cover_image` | path to .jpg/.png — overrides cover_frame_seconds |
| pacing | `daily_cap` | int; default 25 |
| pacing | `pace_seconds` | int; default 300 (5 min) |
| alerts | `notify_email` | recipient for session-expired / cooldown emails |

## Per-video sidecar

`videos/foo.mp4` next to `videos/foo.yaml` → that YAML overlays defaults (deep merge). Use for per-Reel captions and tagged people.

```yaml
caption: |
  New tutorial 🎥
  #react #javascript #performance
location: "San Francisco, California"
collaborators: ["@friend_handle"]
topics: [technology, science]
```

## The upload sequence (verified working — running.rahul.25, 2026-04-25)

```
 1. open      https://www.instagram.com/                          # IG home
 2. wait      6 sec for sidebar render
 3. click     sidebar link "New post"                             # the `+` icon
 4. click     "Post" submenu item                                 # not "Reel" — IG auto-detects
 5. wait      "Create new post" modal heading appears
 6. assert    input[type=file][accept*="video"] is exactly 1      # CRITICAL — see below
 7. upload    input[type=file][accept*="video"]   <video path>
 8. wait      "Crop" heading appears (~20 sec for 12 MB clip)
 9. click     "Next"                                              # accept default crop
10. wait      "Edit" heading appears
11. click     "Next"                                              # skip filters/trim
12. wait      "New reel" heading appears
13. fill      "Write a caption..." textbox  ← cfg.caption OR derived from filename
14. (optional) fill "Add Location" + click first autocomplete result
15. (optional) expand "Advanced Settings" + toggle hide_likes, disable_comments,
              crosspost_to_facebook
16. click     "Share"
17. wait      "Your reel has been shared." text (20–90 sec sharing time)
18. extract   reel URL from a[href*="/reel/"] in confirmation dialog
              (fall back to polling profile /reels/ page if not in dialog)
19. delete    source mp4 + sidecars; append posted.log
```

`scripts/upload-one.py <video-path>` implements this. Re-snapshot before every interactive step — IG composer rebuilds DOM at every step transition, refs go stale.

### Critical selector — file input

IG's create modal renders **3 hidden `<input type=file>` elements**:
- index 0: `accept="image/jpeg"` (story picker)
- index 1: `accept="image/jpeg,image/png"` (profile picture picker)
- index 2: `accept="image/avif,image/jpeg,image/png,image/heic,image/heif,video/mp4,video/quicktime"` ← only this one accepts video

Generic `input[type=file]` selector hits index 0 and silently drops the video — no error, no progress bar. You **must** scope to `input[type=file][accept*="video"]`. We verified this is the difference between "modal stays on Drag prompt forever" and successful upload.

### Auto-caption from filename

If `caption:` in the resolved YAML is empty/null, the skill builds one from the filename: `Journey begins.mp4` → `"Journey begins.\n\n#JourneyBegins #Journey #Begins #Reels"`. Stopwords excluded. Override per-video by dropping `videos/<name>.yaml` with a real `caption:`. For visual-aware captions (smarter than filename), edit `videos/<name>.yaml` by hand — no LLM call in the script.

### Account state — Creator required for video upload

Personal Instagram accounts (default for new accts) **cannot upload videos via web**. The composer accepts the file then shows a tiny "Upload failed. Only images can be posted." toast at the bottom. The skill detects this and exits 78. To unblock: in the user's Chrome, Settings → Account type and tools → Switch to Professional Account → Creator (Personal blog or similar category). Wait ~30 sec for the sidebar to refresh; video upload then unlocks. No retry needed in the skill — exit 78 puts the file in `failed/` and waits for the user to convert.

### Music limitation

Music picker is **not exposed on IG web for newly-converted Creator accounts**. The YAML's `music_search` / `music_track_url` / `music_volume` fields are valid spec but currently inert; IG enables the music library days–weeks after Creator conversion. Until then, source audio is preserved as-is (or muted via `mute_original_audio: true` on the Edit page). Music can always be added on a per-Reel basis through the IG mobile app.

## Queue mode

`scripts/upload-queue.sh [project-dir]`:

1. `preflight.sh`. Halt with clear message on any failure.
2. Check for cooldown file. If present and not expired, exit 0.
3. Count today's lines in `posted.log` — if `>= daily_cap`, exit 0.
4. Find oldest video in `videos/`.
5. Load defaults + sidecar.
6. Call `upload-one.py`.
7. Move file or delete source per outcome.
8. Sleep `pace_seconds`, loop.

Run from launchd / cron every 30 min. Sample plist at `references/launchd.plist`.

## Failure handling

| Symptom | Action |
|---------|--------|
| `instagram.com` redirects to `/accounts/login/` | Email user via `notify_email`, halt queue. |
| "We limit how often you can do certain things" modal | Write `logs/ig-cooldown.until=<now+24h>`, email user, halt entire queue for 24 h. |
| 2FA challenge mid-flow | Halt + email. User completes 2FA in browser; next queue fire resumes. |
| Cropper Next button disabled | Video aspect wrong. Move to `failed/`, `.error` says "non-9:16 — pre-process to 1080×1920". |
| "This action wasn't completed because it goes against our community guidelines" | Move to `failed/`, no retry. Caption probably has banned content. |
| "Try again later" toast on Share | Single retry after 30 sec, then fail. |
| Reel URL doesn't appear on profile within 90 sec | Save with `<filename>.pending` sidecar; next queue run polls again to resolve. |

## Selectors that drift

Instagram changes its DOM constantly. Current values in `references/selectors.md`. When something stops clicking:

1. `agent-browser --auto-connect screenshot /tmp/ig-debug.png` and look at it.
2. `agent-browser --auto-connect snapshot` (no `-i`) for full StaticText.
3. Update `references/selectors.md`, comment old label for history.

Prefer `find role button --name "X"` and `find text "X"` over `@eN` refs — IG composer rebuilds DOM frequently.

## When this skill is invoked

1. Run `scripts/preflight.sh`. Surface failures plainly. Don't proceed.
2. Single video by path → `scripts/upload-one.py <path>`.
3. "Upload everything in videos/" / "run the daily IG upload" → `scripts/upload-queue.sh`.
4. Return Reel URL on single upload, summary on queue.
5. On halt: tell user the exact action needed (sign back in, wait out cooldown, fix aspect ratio).

## What's deliberately out of scope

- **Instagram Graph API.** User wants browser automation; do not propose API path.
- **Multi-account.** Single IG account per project. Multi-account = separate project dirs.
- **Stories, Carousels, Live.** Reels only. Stories are gone after 24 h so not interesting for queue uploads; Carousels need multi-file logic.
- **Automated 2FA.** Must be human at the keyboard.
