# Instagram composer selectors (verified 2026-04-25 on running.rahul.25 Creator)

When something stops clicking:
1. `agent-browser --auto-connect screenshot /tmp/ig-debug.png`
2. `agent-browser --auto-connect snapshot` (no `-i`) for full StaticText
3. Update this file AND the `SELECTORS` dict in `scripts/upload-one.py`

Prefer text-based locators over `@eN` refs — IG composer rebuilds DOM on every step.

## Sidebar / navigation

| Element | role | accessible name | notes |
|---------|------|-----------------|-------|
| New post | link | "New post" | sidebar `+` icon; opens floating Create menu |
| Post submenu | div[role=button] / link | "Post" | unified composer for photos/videos; auto-detects 9:16 → Reel |
| Live video | link | "Live video" | not used by skill |
| Ad | link | "Ad" | not used by skill |

## Create new post modal (initial state)

| Element | role | accessible name | notes |
|---------|------|-----------------|-------|
| Modal heading | h1 | "Create new post" | wait for this to confirm modal opened |
| Drag prompt | h3 | "Drag photos and videos here" | always present |
| Select button | button | "Select From Computer" | fallback if file input direct-set fails |
| **Video file input** | hidden `<input type=file>` | CSS `input[type=file][accept*="video"]` | **CRITICAL** — IG renders 3 file inputs on the page; only the third (in this modal) accepts video. Generic `input[type=file]` picks the wrong one and silently drops the video. |
| Image-only inputs (other 2) | hidden `<input type=file>` | accept="image/jpeg,image/png" | story/profile picture pickers — never use these |

## Crop page

| Element | role | accessible name |
|---------|------|-----------------|
| Heading | h1 | "Crop" |
| Aspect picker | button (bottom-left icon) | (no label) |
| Zoom | button (bottom-right) | (no label) |
| Next | link | "Next" |

## Edit page (filters / cover / trim)

| Element | role | accessible name |
|---------|------|-----------------|
| Heading | h1 | "Edit" |
| Cover photo | section | "Cover photo" + frame strip + "Select From Computer" link |
| Trim | section | "Trim" + range slider |
| Mute toggle | switch | "Video has no audio" — labels swap based on source audio presence |
| Next | link | "Next" |

## New reel page (the publish form)

| Element | role | accessible name | notes |
|---------|------|-----------------|-------|
| Heading | h1 | "New reel" | (or "New post" for non-Reel image posts) |
| Caption | textbox | "Write a caption..." | ≤2200 chars; inline `#hashtags` and `@mentions` work |
| Char counter | static | "0/2,200" | next to caption box |
| Tag People | button | "Tag People" | overlay on video thumbnail |
| Add Location | textbox | "Add Location" | autocomplete dropdown; first suggestion clickable |
| Add collaborators | button | "Add collaborators" | search dialog (max 3) |
| Accessibility | accordion | "Accessibility" | expands → alt text textbox |
| Advanced Settings | accordion | "Advanced Settings" | expands → toggles below |
| Share | button | "Share" | top-right |

## Advanced Settings (when accordion expanded)

| Element | role | accessible name |
|---------|------|-----------------|
| Hide likes/views | checkbox | "Hide like and view counts" |
| Disable comments | checkbox | "Turn off commenting" |
| Crosspost to FB | checkbox | "Also share to Facebook" / "Recommend on Facebook" |
| Audience 18+ | checkbox | "Audience for 18+" / "Restrict to 18+" |

## Music picker

**Not exposed on IG web for newly-converted Creator accounts.** IG enables the
music library days–weeks after Creator conversion. YAML fields `music_search`,
`music_track_url`, etc. are valid spec but inert on web until enabled. To add
music: use IG mobile app for that one Reel.

When music IS available, expect (unverified):
- Button "Add audio" / "Add music" on Edit or New reel page
- Modal with search box + track results list
- Each result a button; click → applies, returns to composer

## Confirmation dialog (after Share)

| Element | role | accessible name |
|---------|------|-----------------|
| Wait state | dialog | title "Sharing" + spinner |
| Final state | dialog | title "Reel shared" |
| Heading | h1 | "Reel shared" |
| Subhead | h3 | "Your reel has been shared." |
| URL anchor | a[href*="/reel/"] | href = `https://www.instagram.com/<handle>/reel/<id>/` ← extract here |

Sharing typically takes 20–90 sec for a 12 MB / 22 sec Reel.

## Blockers (fatal — exit codes in skill)

| Text on page | Meaning | Skill exit code |
|------|---------|--------|
| "We limit how often you can do certain things" | Anti-spam soft-block | 77 → 24h cooldown |
| "We restrict certain activity to protect our community" | Account flagged | 77 → 24h cooldown |
| "Only images can be posted" | Personal account, no video upload right | 78 → tell user to convert to Creator |
| "...goes against our community guidelines" | Caption rejected | 71 → mark failed, no retry |
| URL contains `/accounts/login` or `/challenge` | Session expired or 2FA | 75 → halt + email |

## Per-account state

`running.rahul.25` (verified 2026-04-25):
- Account type: **Creator** (just converted; took ~5 min for sidebar to refresh and show Dashboard / Profile entries)
- Music library: **NOT YET ENABLED** on web — picker absent
- Personal-acct fallback (image-only) seen before conversion: "Upload failed. Only images can be posted."
