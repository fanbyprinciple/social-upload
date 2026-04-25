# Studio selectors (snapshot of accessible names — verified 2026-04-25)

YouTube Studio's UI changes every few months. When a click stops working,
update this file with the new label and comment out the old one for history.
Prefer text-based locators (`find role <role> --name "X"`, `find text "X"`)
over `@eN` refs — refs shift every time Studio rebuilds the DOM.

## Upload dialog (after navigating to https://www.youtube.com/upload)

| Element | role | accessible name | notes |
|---------|------|-----------------|-------|
| File picker | hidden input | (no label — use CSS selector `input[type=file]`) | exactly 1 on the page when dialog is open |
| Close dialog | button | "Close" | also "X" icon |

## Details tab

| Element | role | accessible name |
|---------|------|-----------------|
| Title | textbox | "Add a title that describes your video (type @ to mention a channel)" — required |
| Description | textbox | "Tell viewers about your video (type @ to mention a channel)" |
| Thumbnail upload | button | "Upload file" |
| Auto-generated thumbnail | button | "Auto-generated" |
| A/B testing | button | "A/B Testing" |
| Playlists picker | button | "Select playlists" |
| Made for kids: yes | radio | "Yes, it's made for kids . Features like personalized ads ..." |
| Made for kids: no | radio | "No, it's not made for kids" |
| Age restriction | button | "Age restriction (advanced)" |
| Show advanced settings | ytcp-button | "Show more" — JS-click to expand; DOM rebuilds, ALL refs go stale |

## Details → Show more (advanced) — visible only after expansion

| Element | role | accessible name |
|---------|------|-----------------|
| Paid promotion | checkbox | "My video contains paid promotion like a product placement, sponsorship, or endorsement" |
| Altered: yes | radio | "Yes, it includes altered content" |
| Altered: no | radio | "No, it doesn't include altered content" — note the curly apostrophe |
| Auto chapters | checkbox | "Allow automatic chapters and key moments" |
| Auto places | checkbox | "Allow automatic places" |
| Auto concepts | checkbox | "Allow automatic concepts" |
| Tags | textbox | "Tags" |
| Video language | button | "Video language Select" → opens dropdown |
| Caption certification | button | "Caption certification None" |
| Recording date | button | "Recording date None" → opens date picker |
| Video location | textbox | "Video location" |
| License | button | "License Standard YouTube License" → opens dropdown |
| Allow embedding | checkbox | "Allow embedding" |
| Notify subscribers | checkbox | "Publish to subscriptions feed and notify subscribers" |
| Shorts remixing | radio | "Allow video and audio remixing" / "Allow only audio remixing" / "Don't allow remixing" |
| Category | button | "People & Blogs" (label = current selection) |
| Comments | button | "Comments On" |
| Comment moderation | button | "Moderation Basic" |
| Who can comment | button | "Who can comment Anyone" |
| Comment sort | button | "Sort by Top" |
| Show like count | checkbox | "Show how many viewers like this video" |

## Wizard advancement

| Element | role | accessible name |
|---------|------|-----------------|
| Next | button | "Next" — disabled until kids + altered selected |
| Back | button | "Back" |
| Save (final step) | button | "Save" — sometimes "Publish" depending on Studio version |

## Video elements tab

| Element | role | accessible name |
|---------|------|-----------------|
| Add subtitles | button | "Add" (under "Add subtitles" heading) |
| Add end screen | button | "Add" (under "Add an end screen") + "Import from video" |
| Add cards | button | "Add" (under "Add cards") |

## Checks tab

Auto-runs Copyright + Ad-suitability scan. No interactive controls unless an issue is flagged.

## Visibility tab

| Element | role | accessible name |
|---------|------|-----------------|
| Private | radio | "Private" |
| Unlisted | radio | "Unlisted" |
| Public | radio | "Public" |
| Instant Premiere | checkbox | "Set as instant Premiere" — only enabled when Public |
| Schedule | button | "Click to expand" (under "Schedule" heading) |
| Save | button | "Save" |

## Confirmation dialog (after Save)

| Element | role | accessible name |
|---------|------|-----------------|
| Heading | heading level 1 | "Video published" or "Video saved" |
| Share link | link | `https://youtu.be/<id>` ← extract URL from here |
| Copy link | button | "Copy video link" |
| Close | button | "Close" |
