# Moto Razr → social-upload integration

How the Moto Razr GIF clockface pipeline (`Moto_Razr/`) feeds rendered MP4s into these skills, plus the YouTube Studio quirks we learned producing the first live upload.

First successful upload: **<https://youtube.com/shorts/XF-XOMIwXhk>** (Unlisted, on Presto Cranius test channel) — `vinyl-record.mp4` rendered with the `freepd-ambient-a-zyow.mp3` track.

---

## End-to-end shape

```
Moto_Razr/GIF Store/<source>.gif
    ↓ /process-razr-gif
Moto_Razr/processed/<slug>-<ClockLayout>.mp4
    ↓ stage (copy + write sidecar from processed_gifs.json captions)
~/codeplay/socials/youtube-upload/videos/<slug>.mp4
~/codeplay/socials/youtube-upload/videos/<slug>.yaml
    ↓ /youtube-upload
youtube.com/shorts/<id>      ← URL appended to videos/posted.log
```

The producing pipeline (Moto Razr) writes per-platform captions into `processed_gifs.json`:

```json
{
  "slug": "vinyl-record-CenterEnd",
  "outputVideo": ".../processed/vinyl-record-CenterEnd.mp4",
  "musicTrack": "freepd-ambient-a-zyow.mp3",
  "captions": {
    "youtube_title":       "Moto Razr GIF Clockface - Vinyl Record",
    "youtube_description": "GIF clockface for Moto Razr cover screen. ...\n#motorazr #coverscreen #clockface #razr #livewallpaper",
    "instagram":           "...",
    "tiktok":              "..."
  }
}
```

Staging into a project copies the chosen MP4 and writes a `<slug>.yaml` sidecar:

```yaml
title: "Moto Razr GIF Clockface - Vinyl Record #shorts"
description: |
  GIF clockface for Moto Razr cover screen.

  Anime vinyl record player spinning with warm cozy vibes.

  Get this clockface: https://ijp.app/cf/vinyl-record
  ...
tags: [shorts, motorazr, motorola, razr, coverscreen, clockface, livewallpaper]
```

The skills consume this verbatim — there is **no filename auto-derive** for title/description/caption. If the sidecar is missing those fields, the upload script exits with a clear error (intentional contract — Moto Razr is the source of truth).

---

## ⚠️ Music safety guardrail (hard-learned)

YouTube Content ID flagged `playful-chiptune.mp3` (catalog `source: "local"`) on our first attempt. The same flow with `freepd-ambient-a-zyow.mp3` (`source: "freepd"`, FreePD.com — verified CC0) passed cleanly with **"Checks complete. No issues found."**

**Rule:** when staging from `Moto_Razr/processed_gifs.json` for any of these skills, only pick records whose `musicTrack` starts with `freepd-`. The 8 catalog tracks marked `source: "local"` have unverified provenance and trigger Content ID matches.

```bash
# Find safe candidates
python3 -c "
import json, os
d = json.load(open('Moto_Razr/processed_gifs.json'))
for r in d['gifs']:
    if (r.get('musicTrack','') or '').startswith('freepd-') \
       and os.path.exists(r.get('outputVideo','')) \
       and (r.get('captions',{}) or {}).get('youtube_title'):
        print(r['slug'], '|', r['musicTrack'])
"
```

---

## YouTube Studio quirks we learned (logged for future Studio drift)

### 1. Title field — JS `execCommand`, not ref-based fill

Studio's title is a contenteditable `<div>`, not an `<input>`. `agent-browser fill` against the contenteditable's ref **appends** instead of replacing — produces concatenated titles like `"<filename>Moto Razr GIF Clockface - …"`.

**Fix:** `set_contenteditable_by_aria("Add a title", text)` — find the contenteditable by aria-label substring and run `execCommand('selectAll'); execCommand('delete'); execCommand('insertText', false, text)`. This is what Studio's own JS does on a real keystroke and fires the events React listens for.

Same pattern for description (aria-label: `"Tell viewers about your video"`).

### 2. Radios have `aria-label = null`

Studio's radios are `<tp-yt-paper-radio-button>` web components with **no aria-label**. The original ref+click pattern silently no-op'd because the click target needs to be the inner shape.

**Fix:** match by `textContent` instead. Helper `click_radio_by_text(label, exact=False)`. Use `exact=True` for short ambiguous labels (`"Yes"` / `"No"`) to avoid colliding with the longer kids labels.

### 3. Altered-content radios are `"Yes"` / `"No"` (NOT verbose)

The script previously assumed `"Yes, it includes altered content"` / `"No, it doesn't include altered content"` — those don't exist in Studio's DOM. Use exact-match `"Yes"` / `"No"`. They appear right after the Made-for-kids and Age-restriction radios in DOM order.

### 4. There are TWO `<button>`s named "Save" — one is a wrapper that no-ops

Studio's publish flow renders `<ytcp-button id="done-button">` (the real publish) and an inner `<button>` shape with the same text. Naive `find role button click --name "Save"` lands on the inner shape and does nothing.

**Fix:** target `#done-button` by id. Helper `click_save_button()`. Falls back to text-based search if the id is ever renamed.

### 5. `session-check.sh` must switch tabs before reading cookies

`agent-browser cookies get` returns cookies for the **active tab's origin** only. If the current tab is `about:blank` or a non-Google site, the Google session cookies (SAPISID/SID/HSID) won't appear and preflight will report "session expired" even though the user is signed in.

**Fix:** `session-check.sh` now `tab list`s for an existing youtube/google tab and switches to it before the cookie probe. If none exists, it opens `https://www.youtube.com/` (homepage, NOT Studio — opening Studio repeatedly trips Google's automation heuristics).

---

## Required preconditions on the upload Mac

1. **Opera/Chrome running on `--remote-debugging-port=9222`** with the `~/.youtube-upload-chrome-profile` profile dir, and signed in to YouTube Studio (the user does this once via `chrome-launch.sh` or by pre-launching Opera with these flags).
2. `agent-browser` installed (`npm i -g agent-browser`).
3. PyYAML (`pip install --break-system-packages pyyaml`).
4. `~/codeplay/socials/youtube-upload/upload-defaults.yaml` exists with at minimum `visibility`, `made_for_kids`, `altered_content`, and `notify_email` set. **Do not** put title/description there — those come per-video from the staged sidecar.

---

## Failure modes worth remembering

| Symptom | Likely cause | Action |
|---|---|---|
| Upload completes but result is "Draft" | Save click landed on the wrapper button | Already fixed via `click_save_button()` (`#done-button`) |
| Title shows `<filename><yourtitle>` concatenated | Ref-based fill on contenteditable | Already fixed via `set_contenteditable_by_aria` |
| Details tab still shows orange ! after Show more | Made-for-kids selection lost on DOM rebuild | Script re-clicks kids after Show more — keep that |
| Preflight reports "session expired" even though you're signed in | session-check probed wrong tab | Already fixed; `session-check.sh` switches tabs |
| Studio shows "Copyright-protected content found" on Checks tab | `local` music track in `Moto_Razr/public/music/catalog.json` | Stage only MP4s with `freepd-*` musicTrack |
| Visibility radio "Unlisted not found" | Earlier wizard step blocked progression (kids/altered not set) | Snapshot the page; the script's WARN logs will say which radio missed |
