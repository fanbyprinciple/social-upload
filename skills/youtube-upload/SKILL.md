---
name: youtube-upload
description: Upload videos to YouTube — one or many — by driving YouTube Studio's web UI through agent-browser attached to a real, signed-in Chrome. Use this skill whenever the user wants to publish videos to their YouTube channel, queue uploads from a folder, schedule a recurring uploader, set Studio metadata (title, description, tags, visibility, kids/altered disclosures, category, language, comments, playlists, premiere, schedule), recover from session expiry, or work with the youtube-upload app at CSOS/socials/youtube-upload. Strong triggers — "upload to youtube", "publish video to youtube", "queue youtube uploads", "youtube studio", "youtube uploader", "auto upload videos", "post videos to youtube", "bulk upload youtube", "drop videos in folder and upload daily", "youtube upload from yaml", "schedule youtube upload". Use proactively whenever the user references uploading any video file to a YouTube channel, even if they don't name this skill.
---

# YouTube upload (browser-driven)

Drives YouTube Studio's upload wizard end-to-end by attaching `agent-browser --auto-connect` to a Chrome window the user has signed into. Reads metadata from a YAML defaults file (with optional per-video sidecar), uploads the oldest pending video in a folder, publishes per the YAML, deletes the source file on success, logs the YouTube URL.

Designed for single-channel use, sustained over days. Public by default. Private + scheduled supported through YAML.

## Why driving real Chrome (and not the Data API)

We deliberately do not use the YouTube Data API. The user wants browser automation. Use it.

The skill MUST attach to a *real* Chrome via `agent-browser --auto-connect` on CDP port 9222. Do **not** use agent-browser's bundled Chromium with `state save` / `state load`. Google detects that fingerprint and blocks sign-in with "browser may not be secure"; even when cookies are imported, every navigation to `studio.youtube.com` redirects to `accounts.google.com`. Verified twice — there is no workaround. The only path that survives Google's automation detection is driving the user's own Chrome.

This means auth is half-manual. The user runs Chrome once with a debug port and signs in; the skill rides that session for as long as Google honors the cookie (~2 weeks). On expiry the skill emails the user and halts — it cannot self-recover.

## Prerequisites checklist (run every invocation)

Use `scripts/preflight.sh`. It checks all four:

1. `agent-browser` is installed and on PATH.
2. Chrome is alive at `http://localhost:9222/json/version`. If not, suggest `scripts/chrome-launch.sh`.
3. The session is signed into Studio — `agent-browser --auto-connect open https://studio.youtube.com` returns a `studio.youtube.com/...` URL, not `accounts.google.com/...`.
4. A defaults YAML is reachable. Resolution order: explicit `--config` arg, `$YT_UPLOAD_PROJECT/upload-defaults.yaml`, `$PWD/upload-defaults.yaml`, `$HOME/codeplay/ijp_research/CSOS/socials/youtube-upload/upload-defaults.yaml`.

If any check fails, surface the failure plainly to the user and stop. Don't try to substitute or guess your way around missing auth.

## One-time user setup

The user runs (in their own terminal — these need a TTY for the Google sign-in):

```bash
~/.claude/skills/youtube-upload/scripts/chrome-launch.sh
# A Chrome window opens. Sign in to YouTube Studio in it.
```

That window must keep running for the skill to work. The profile lives at `$HOME/.youtube-upload-chrome-profile` so cookies survive Chrome restarts; the user only has to repeat sign-in when Google rotates the session (~2 weeks).

## File layout

```
<project>/                           # default: $HOME/codeplay/ijp_research/CSOS/socials/youtube-upload/
├── upload-defaults.yaml             # global defaults — applies to every upload
├── videos/
│   ├── <name>.mp4                   # drop new videos here; oldest mtime goes first
│   ├── <name>.yaml                  # OPTIONAL — overlays defaults for this one video
│   ├── <name>.jpg                   # OPTIONAL — custom thumbnail (matches stem)
│   ├── posted.log                   # success → filename + URL appended (NO video kept)
│   └── failed/<name>.{mp4,error}    # failure → file moved here + .error sidecar
└── logs/upload.log                  # appended; rotated at 10 MB
```

On success the source `.mp4` is **deleted** (along with sidecar `.yaml`/`.jpg`) and the upload is recorded in `videos/posted.log`. The user explicitly does not want posted videos kept on disk — the YouTube URL is the canonical artifact.

## upload-defaults.yaml — schema

Every key optional except `visibility`, `made_for_kids`, `altered_content` (Studio refuses to advance without these). Null/empty = "leave Studio default — don't touch the field". The reference file at `assets/upload-defaults.template.yaml` is the canonical, fully-commented version.

| Section | Key | Values |
|---------|-----|--------|
| required | `visibility` | `public` (default) \| `unlisted` \| `private` |
| required | `made_for_kids` | `true` \| `false` |
| required | `altered_content` | `true` \| `false` (AI/synthetic disclosure) |
| basic | `title` | string; null → derive from filename stem (hyphens/underscores → spaces, title-case) |
| basic | `description` | multiline string; null → auto-built from title as `"<title>\n\n#<TitlePascal> #Word1 #Word2"` (stopwords excluded) |
| basic | `tags` | list of strings; null/`[]` → auto-derived from title words (stopwords excluded); joined by comma in Studio (≤500 chars total) |
| basic | `category` | `People & Blogs` \| `Education` \| `Entertainment` \| `Gaming` \| `Music` \| `Comedy` \| `Film` \| `News` \| `How-to` \| `Pets` \| `Science` \| `Sports` \| `Travel` \| `Nonprofits` \| `Auto` |
| advanced | `paid_promotion` `automatic_chapters` `automatic_places` `automatic_concepts` `allow_embedding` `notify_subscribers` `show_likes` | bool; defaults match Studio defaults so omit unless overriding |
| advanced | `license` | `standard` \| `creative_commons` |
| advanced | `shorts_remixing` | `video_and_audio` \| `audio_only` \| `none` |
| advanced | `comments` | `on` \| `off` |
| advanced | `comment_moderation` | `basic` \| `strict` \| `hold_all` \| `off` |
| advanced | `who_can_comment` | `anyone` \| `subscribers` \| `approved` |
| advanced | `comment_sort` | `top` \| `newest` |
| advanced | `video_language` `caption_certification` `recording_date` `video_location` | strings |
| visibility | `premiere` | bool; only valid when `visibility=public` |
| visibility | `schedule` | ISO 8601 datetime e.g. `2026-05-01T14:00:00`; **automatically forces `visibility=private`** when set |
| pacing | `daily_cap` | int; default 50; halts queue when today's count reaches it |
| pacing | `pace_seconds` | int; default 60 — sleep between uploads in queue mode |
| alerts | `notify_email` | string; recipient for session-expired email; defaults to whoever the Chrome window is signed in as |

## Per-video sidecar

If `videos/foo.mp4` has `videos/foo.yaml` next to it, the sidecar overlays the global defaults — only the keys it sets get changed. Use this for per-video titles, custom tags, scheduled publish times. Most uploads will use defaults only; sidecars are the escape hatch.

```yaml
title: "Why React Re-renders"
tags: [react, javascript, performance]
description: |
  Deep dive into useMemo and reference equality.
schedule: 2026-05-15T09:00:00   # implicitly sets visibility=private until that time
```

## The upload sequence (verified working)

This is the exact path that works against Studio today. Refs (`@eN`) shift after every DOM rebuild, so re-snapshot before every interactive step. Reusing a stale ref clicks the wrong element silently.

```
 1. open      https://www.youtube.com/upload                    # redirects to studio with ?d=ud
 2. wait      6–8 sec for the upload dialog to render
 3. assert    document.querySelectorAll('input[type=file]').length === 1
 4. upload    input[type=file]   <video path>
 5. wait      10–16 sec for upload to start + Details tab to render
 6. snapshot  -i, find: title input, description input, kids No radio
 7. fill      description (defaults.description)
 8. click     kids No radio
 9. JS click  "Show more" button (advanced settings expand)         # DOM REBUILDS — refs go stale
10. snapshot  -i again, re-find every ref you need
11. click     kids No radio AGAIN (selection lost when DOM rebuilt)
12. click     altered No radio
13. (optional) set advanced fields that differ from defaults — each click costs another snapshot
14. click     Next  → Video elements
15. click     Next  → Checks (Studio auto-runs copyright/ad-suitability scan)
16. click     Next  → Visibility
17. snapshot  -i, find visibility radio matching defaults.visibility
18. click     visibility radio
19. (if schedule set) expand schedule, fill date, fill time
20. click     Save
21. wait      3–5 sec for "Video published" / "Video saved" dialog
22. extract   /https:\/\/youtu\.be\/[A-Za-z0-9_-]+/ from snapshot
23. click     Close
24. delete    source <video>.mp4 (and sidecar .yaml/.jpg if present)
25. append    "<iso-timestamp>  <filename>  <url>" to videos/posted.log AND logs/upload.log
```

`scripts/upload-one.sh <video-path>` implements this. Don't reimplement inline — the script handles the timing waits, ref re-snapshotting, and partial-failure cleanup.

## Queue mode — uploading thousands across days

`scripts/upload-queue.sh` runs the loop:

1. `preflight.sh`. Halt with clear message on any failure.
2. Count today's lines in `posted.log` — if `>= daily_cap`, exit 0 (next launchd fire will pick up tomorrow).
3. Find oldest `.mp4`/`.mov`/`.m4v`/`.webm` in `videos/` (ignoring `failed/` subdir).
4. Load defaults, overlay sidecar if present.
5. Call `upload-one.sh`.
6. On success: source already deleted by upload-one; loop continues.
7. On failure: source moved to `failed/` with `<name>.error` sidecar; loop continues.
8. Sleep `pace_seconds` between iterations.
9. Halt entirely if `preflight.sh` fails mid-loop (session expired during a long run).

Run from launchd / cron — fire `upload-queue.sh` every 5–10 minutes. Internal pacing + daily cap throttle naturally. Sample plist at `references/launchd.plist`.

## Failure handling

| Symptom | What the skill does |
|---------|---------------------|
| Preflight fails: Chrome not at :9222 | Tell user to run `scripts/chrome-launch.sh`. Do not auto-launch — Chrome needs the user's keyboard for sign-in anyway. |
| Preflight fails: redirected to `accounts.google.com` | Send email to `notify_email` via `scripts/notify-email.sh`, halt. |
| Studio returns "Daily upload limit reached" | Move file back to `videos/` (not failed/), append "RATE-LIMIT" line to log, exit 0. Tomorrow's queue retries. |
| `input[type=file]` count is 0 after open | Reload the upload URL once, wait 10 sec, retry. If still 0, mark video failed. |
| Snapshot grep for `youtu.be/...` returns nothing post-Save | Wait 5 sec, re-snap. Still nothing → screenshot to `logs/<name>-debug.png`, mark failed (manual cleanup needed). |
| Captcha appears mid-flow | Mark failed with `.error` saying "captcha — solve it manually in the browser, then move file from failed/ back to videos/". |
| Stale dialog from prior crashed run | At start of upload-one.sh, if URL contains `?d=ud` and a dialog is detected, click Close before opening the upload again. |

When halted by session expiry, exit cleanly. Don't retry inside the same invocation — the user must do something physical (sign back in to Chrome).

## Selectors that drift

Studio aria-labels change every few months. Current values are in `references/selectors.md`. When something stops clicking:

1. Take a screenshot — `agent-browser --auto-connect screenshot /tmp/studio-debug.png`.
2. Snapshot full (`agent-browser --auto-connect snapshot`, no `-i`) to read all StaticText labels.
3. Update `references/selectors.md` with the new label, comment out the old one for history.

Prefer `find role button --name "X"` and `find text "X"` over `@eN` refs whenever possible. Text locators survive DOM rebuilds; refs do not.

## When this skill is invoked

1. Run `scripts/preflight.sh`. Surface any failure in plain language. Don't proceed.
2. Pick mode:
   - "upload this video <path>" → `scripts/upload-one.sh <path>`
   - "upload everything in videos/" or "run the daily upload" or no specific video → `scripts/upload-queue.sh`
3. After single upload: return the YouTube URL. After queue: summarize "N uploaded, M pending, K failed" + the URLs.
4. On any halt (session expired, cap reached): tell the user the exact thing they need to do to resume. Don't dress it up.

## What's deliberately out of scope

- **YouTube Data API v3 / OAuth.** User wants browser automation; do not propose API as a fallback.
- **Multi-channel.** Single channel only. If the user later wants multi-channel, separate Chrome profiles per channel + per-channel project dirs would be the way.
- **Chrome auto-launch with sign-in.** Sign-in needs a human at the keyboard. Skill helps launch Chrome but cannot complete sign-in.
- **Retries inside one invocation past the first preflight failure.** Let the next scheduled fire handle it.
