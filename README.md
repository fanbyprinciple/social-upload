# social-upload

Three Claude Code skills that publish video content to YouTube, Instagram Reels, and TikTok — driven from YAML defaults, queueable from a folder, with conservative anti-spam pacing.

| Skill | Backend | Verified |
|---|---|---|
| [`youtube-upload`](skills/youtube-upload/) | YouTube Studio web UI via `agent-browser` against real Chrome/Opera | ✅ |
| [`instagram-upload`](skills/instagram-upload/) | `instagram.com` web composer via `agent-browser` | ✅ |
| [`tiktok-upload`](skills/tiktok-upload/) | TikTok Content Posting API (preferred) with `studio.tiktok.com/upload` agent-browser fallback | partial — selectors need first-run verification |

Each skill follows the same pattern:
- Read `upload-defaults.yaml` from the project dir, deep-merge optional `videos/<name>.yaml` sidecar
- Auto-derive the caption/description from the filename when YAML field is empty
- Pick the oldest video in `videos/`, drive the platform's web composer or API, delete the source on success
- Append `<iso-timestamp>\t<filename>\t<url>` to `videos/posted.log`
- Move failed files to `videos/failed/` with a `.error` sidecar
- Halt cleanly on session expiry / soft-block, send an email to `notify_email`

---

## Install

```bash
git clone https://github.com/<your-username>/social-upload.git
cd social-upload
./install.sh                 # all 3 skills
# or:  ./install.sh youtube-upload
```

`install.sh` copies each skill into `~/.claude/skills/<name>/` and bundles the shared `chrome-launch.sh` + `notify-email.sh` into each skill's `scripts/` dir.

After install, the skills auto-trigger in any Claude Code session — Claude sees them in the available-skills list and uses them when you say things like "upload this to youtube" or "post to instagram".

### For Claude agents installing this bundle

Read `meta-prompt.md` in the repo root. It tells you (a Claude agent) exactly how to:
- run `./install.sh`
- create the per-platform project folders from `projects-sample/`
- prompt the user to fill `upload-defaults.yaml` + sign in via Opera
- offer to wire up launchd recurring jobs

---

## Project folder pattern

Each platform has a project folder (you create one per account). Sample layouts in [`projects-sample/`](projects-sample/):

```
<project>/
├── README.md
├── upload-defaults.yaml         # global defaults — edit here
├── tiktok-api-creds.yaml        # OPTIONAL — TikTok API mode only (chmod 600)
├── videos/
│   ├── <name>.mp4               # drop here
│   ├── <name>.yaml              # OPTIONAL per-video overlay
│   ├── posted.log               # `<iso>\t<filename>\t<url>`
│   └── failed/
└── logs/
    └── upload.log
```

Copy a sample folder anywhere you want (e.g. `~/codeplay/ijp_research/CSOS/socials/<platform>/`) and edit `upload-defaults.yaml`.

---

## Prerequisites

- macOS or Linux
- Python 3 with PyYAML (`pip install --break-system-packages pyyaml` once)
- [`agent-browser`](https://github.com/agent-browser/agent-browser) — `npm i -g agent-browser && agent-browser install`
- A Chromium-family browser (Chrome / Chromium / Opera / Brave / Edge — all supported via `$YT_BROWSER`)

For each platform the user wants to use:
- A signed-in account (sign in once via the launched browser; cookies persist ~1–4 weeks)
- For YouTube: any account
- For Instagram: **must be Creator or Business** account (Personal accounts can't upload video via web)
- For TikTok: any account; API mode optionally needs OAuth-issued tokens

---

## How auth works (every skill)

The repo's `shared/chrome-launch.sh` opens a real Chromium-family browser with `--remote-debugging-port=9222` and a persistent profile at `~/.youtube-upload-chrome-profile`. **You sign in to each platform once in that window.** The skills attach to that browser via `agent-browser --auto-connect` — no scraped credentials, no headless cookies.

`session-check.sh` for each skill is a passive cookie probe — it never navigates to the platform site. This avoids the anti-spam soft-blocks that bit us during initial development (one IG account got "We restrict certain activity" after repeated session-probe navigations).

---

## Pacing defaults

| Platform | daily_cap | pace_seconds | launchd cadence |
|---|---|---|---|
| YouTube | 50 | 60 | every 10 min |
| Instagram | 25 | 300 (5 min) | every 30 min |
| TikTok | 5 | 3600 (1 hour) | every 1 hour |

These reflect each platform's anti-spam tolerance from worst to best. **Do not raise without thinking** — TikTok permanently bans automated accounts.

---

## What's deliberately out of scope

- Cross-posting from one upload to multiple platforms simultaneously (you queue per-platform)
- Multi-account per platform (use separate project folders)
- Music selection on IG (web composer doesn't expose it for new Creator accts)
- Visual-aware caption generation (filename-derived only — extend per-video via sidecar yaml)
- Automated OAuth setup for TikTok API mode (user runs the OAuth dance once themselves)

---

## Repo layout

```
social-upload/
├── README.md                   (this file)
├── meta-prompt.md              instructions for a Claude agent installing this bundle
├── LICENSE                     MIT
├── install.sh                  install/uninstall script
├── .gitignore
├── shared/
│   ├── chrome-launch.sh        launch Chromium with debug port + persistent profile
│   └── notify-email.sh         macOS banner + optional `mail` send
├── skills/
│   ├── youtube-upload/
│   ├── instagram-upload/
│   └── tiktok-upload/
└── projects-sample/
    ├── youtube-upload/
    ├── instagram-reels/
    └── tiktok-uploads/
```

---

## Moto Razr clockface integration

The first production user of these skills is the [Moto Razr GIF clockface pipeline](MOTO_RAZR_INTEGRATION.md). That doc captures:

- How `processed_gifs.json` captions feed the per-video YAML sidecar (no filename auto-derive — captions come from the producing pipeline as the source of truth).
- The **CC0 music guardrail** discovered when YouTube Content ID flagged a `source: "local"` track: stage only MP4s whose `musicTrack` starts with `freepd-`.
- Five YouTube Studio DOM quirks we hit and fixed (title contenteditable needs `execCommand`, radios have `aria-label=null`, altered-content labels are just `"Yes"`/`"No"`, two overlapping Save buttons, `session-check` must switch to a youtube tab before the cookie probe).

If you're integrating another producing pipeline (not Moto Razr), use `MOTO_RAZR_INTEGRATION.md` as a template — the Studio quirks apply universally; the Razr-specific bits (catalog.json, processed_gifs.json) are easy to swap.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Built collaboratively with Claude Code (Opus 4.7) — full session-by-session learning baked into the SKILL.md files and the `references/selectors.md` per skill.
