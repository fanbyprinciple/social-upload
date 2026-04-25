---
name: tiktok-upload
description: Upload videos to TikTok — one or many — via TikTok Content Posting API (preferred) with agent-browser fallback against studio.tiktok.com/upload. Use this skill whenever the user wants to publish videos to their TikTok account, queue uploads from a folder, schedule a recurring TikTok uploader, set TikTok metadata (caption, hashtags, visibility, allow comments/duet/stitch, AI-generated label, schedule, cover frame), recover from session expiry or anti-spam soft-blocks, or work with the tiktok-uploads app at CSOS/socials/tiktok-uploads. Strong triggers — "upload to tiktok", "post tiktok", "tiktok uploader", "auto upload tiktok", "post videos to tiktok", "bulk upload tiktok", "drop tiktoks in folder and upload daily", "tiktok from yaml", "schedule tiktok upload", "tt upload", "tiktok video upload". Use proactively whenever the user references uploading any video file to a TikTok account.
---

# TikTok upload (API-first, browser-fallback)

Drives TikTok video uploads through two backends:
1. **TikTok Content Posting API** — official, OAuth, no fingerprint games, ~50 posts/day. Preferred when credentials are configured.
2. **studio.tiktok.com/upload via agent-browser** — fallback, works against the same Chrome the IG and YouTube skills use.

Skill auto-picks based on `mode:` in `upload-defaults.yaml` (`api` | `browser` | `auto`). Default `auto` tries API first, falls back to browser if creds missing or API errors.

Designed for low-volume use — defaults are 5 posts/day, 1 hour between posts. TikTok's anti-spam fires faster than IG or YouTube.

## Why both modes

The TikTok Content Posting API is the cleanest path *if* you can set up credentials. But the OAuth dance + app registration takes 20 min the first time and the **`direct` post mode requires manual TikTok audit** (weeks). The auto-approved `inbox` mode posts to your drafts; you tap Publish from the mobile app — useful for safety + review.

The browser path needs no setup but is fragile: TikTok's UI changes monthly, and TikTok Studio's anti-automation can soft-block the account after a handful of programmatic posts. Use it for one-off catchup or when API audit is pending.

## Prerequisites checklist

`scripts/preflight.sh` checks:

1. `agent-browser` on PATH (only required for browser mode)
2. Chrome reachable at `localhost:9222` (only required for browser mode)
3. **For API mode**: `<project>/tiktok-api-creds.yaml` present with `client_key`, `client_secret`, `access_token`
4. **For browser mode**: `sessionid` + `tt_csrf_token` cookies present (passive probe — no tiktok.com navigation)
5. No active cooldown — `logs/tt-cooldown.until` absent or in the past
6. Defaults YAML reachable

## One-time setup

### Browser mode — minimal

```bash
~/.claude/skills/tiktok-upload/scripts/chrome-launch.sh
# In the Opera window: sign in to tiktok.com (if not already)
```

That's it. `session-check.sh` reads cookies passively, never navigates.

### API mode — 20 min

1. Sign up at https://developers.tiktok.com/
2. Create an app, add **Content Posting API** as a product. Sandbox auto-approves the `inbox` endpoint; `direct` needs audit.
3. Run the OAuth user-authorization flow once for your TikTok account. Note the `access_token` and `refresh_token`.
4. `cp ~/.claude/skills/tiktok-upload/assets/tiktok-api-creds.yaml.example <project>/tiktok-api-creds.yaml`
5. Fill in `client_key`, `client_secret`, `access_token`, `refresh_token`. `chmod 600`.

Detailed OAuth setup is out of scope for the skill — see TikTok's docs.

## File layout

```
<project>/                         # default: ~/codeplay/ijp_research/CSOS/socials/tiktok-uploads/
├── README.md                      # how to use this project (auto-created)
├── upload-defaults.yaml
├── tiktok-api-creds.yaml          # OPTIONAL — API mode credentials, chmod 600
├── videos/
│   ├── <name>.mp4                 # drop new videos here
│   ├── <name>.yaml                # OPTIONAL per-video override
│   ├── posted.log                 # filename + URL, one per line
│   └── failed/<name>.{mp4,error}
└── logs/
    ├── upload.log
    └── tt-cooldown.until          # presence = queue paused 24h
```

## upload-defaults.yaml — schema

| Section | Key | Values |
|---|---|---|
| mode | `mode` | `api` \| `browser` \| `auto` (default) |
| basic | `caption` | string ≤2200 chars; null → auto-derived from filename |
| visibility | `visibility` | `public` \| `friends` \| `private` |
| visibility | `allow_comments` `allow_duet` `allow_stitch` | bool |
| disclosures | `ai_generated` | bool — adds "AI-generated content" label |
| disclosures | `audience_age_18plus` | bool |
| schedule | `schedule` | ISO 8601; null = post now; max ~10 days |
| cover | `cover_frame_seconds` | int — frame at N sec |
| cover | `cover_image` | path; overrides cover_frame_seconds |
| copyright | `copyright_check_skip` | bool — ignore pre-publish copyright warning |
| pacing | `daily_cap` | int; default 5 |
| pacing | `pace_seconds` | int; default 3600 (1 hour) |
| alerts | `notify_email` | recipient |

## Auto-caption from filename

If `caption:` empty/null, skill builds one: `Journey begins.mp4` → `"Journey begins.\n\n#JourneyBegins #journey #begins #fyp #foryou"`. Same pattern as IG and YT skills.

## Failure modes

| Symptom | Skill exit | Action |
|---|---|---|
| API auth 401/403 | 75 | Refresh OAuth token; halt + email |
| API rate limit 429 | 77 | 24h cooldown; halt + email |
| Browser session-check finds no cookies | 12 (preflight) | Tell user to sign in to tiktok.com |
| Browser sees "Try again later" / "Daily limit" | 77 | 24h cooldown |
| Browser sees "violates community guidelines" | 71 | Move to failed/, no retry |
| Pre-publish copyright warning | 71 unless `copyright_check_skip: true` | Move to failed/ with explanation |
| Browser composer didn't render | 71 | Single retry then failed/ |
| Browser path returns no URL | 72 | Mark failed; user must verify on profile |

## When this skill is invoked

1. `preflight.sh` — surface failure plainly. Don't proceed.
2. Single video by path → `upload-one.py <path>` (mode read from defaults yaml unless `--mode` overrides).
3. "Upload everything in videos/" → `upload-queue.sh`.
4. Return URL on single, summary on queue.
5. On halt: tell the user the exact action needed.

## What's deliberately out of scope

- **OAuth setup automation.** The user must run the TikTok OAuth flow once themselves; the skill assumes valid `access_token` in `tiktok-api-creds.yaml`. Refresh-on-expiry is implemented; first-token isn't.
- **TikTok app audit / Production approval.** `direct` mode requires it; user owns that process.
- **Music selection in browser mode.** TikTok Studio web has limited music options vs mobile app.
- **Multi-account.** Single TikTok handle per project.
