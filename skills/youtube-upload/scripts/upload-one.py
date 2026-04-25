#!/usr/bin/env python3
"""upload-one.py <video-path> [--config defaults.yaml]

Upload one video to YouTube via Studio web UI driven by agent-browser.
Reads the resolved YAML config (defaults overlaid by per-video sidecar),
performs the verified upload sequence, deletes the source on success,
returns the YouTube URL.

Exit codes:
  0  uploaded; URL printed to stdout
  64 usage error
  66 video file missing
  70 prereq missing (agent-browser, yaml lib, etc.)
  71 Studio interaction failed mid-flow
  75 session expired (not signed in)
  77 daily upload limit hit on YouTube side — caller should requeue
"""

import argparse, os, re, sys, time, subprocess, pathlib, datetime

try:
    import yaml
except ImportError:
    sys.exit("[upload-one] pip install --break-system-packages pyyaml")


def ab(*args, capture=True, timeout=60):
    r = subprocess.run(
        ["agent-browser", "--auto-connect", *args],
        capture_output=capture, text=True, timeout=timeout,
    )
    if capture and r.returncode != 0:
        print(f"[ab] {' '.join(args)} -> rc={r.returncode}: {r.stderr.strip()}", file=sys.stderr)
    return r.stdout.strip() if capture else ""


def snap(interactive=True):
    return ab("snapshot", "-i") if interactive else ab("snapshot")


def find_ref(snapshot, label, role=None):
    label_l, role_l = label.lower(), (role or "").lower()
    for line in snapshot.splitlines():
        ll = line.lower()
        if label_l not in ll:
            continue
        if role_l and role_l not in ll:
            continue
        m = re.search(r"ref=(e\d+)", line)
        if m:
            return f"@{m.group(1)}"
    return None


def click(ref): ab("click", ref)
def fill(ref, text): ab("fill", ref, text)


def deep_merge(base, overlay):
    """Overlay overrides base; nested dicts merged, lists/scalars replaced."""
    if not isinstance(overlay, dict):
        return overlay
    out = dict(base) if isinstance(base, dict) else {}
    for k, v in overlay.items():
        out[k] = deep_merge(out.get(k), v) if isinstance(v, dict) else v
    return out


def load_config(video_path: pathlib.Path, explicit_config: pathlib.Path | None):
    """Resolve defaults YAML + sidecar, merge, return single dict."""
    if explicit_config:
        defaults_path = explicit_config
    else:
        candidates = [
            video_path.parent.parent / "upload-defaults.yaml",
            pathlib.Path.cwd() / "upload-defaults.yaml",
            pathlib.Path.home() / "codeplay/ijp_research/CSOS/socials/youtube-upload/upload-defaults.yaml",
        ]
        defaults_path = next((c for c in candidates if c.exists()), None)
    if not defaults_path or not defaults_path.exists():
        sys.exit("[upload-one] no upload-defaults.yaml found")

    with open(defaults_path) as f:
        cfg = yaml.safe_load(f) or {}

    sidecar = video_path.with_suffix(".yaml")
    if sidecar.exists():
        with open(sidecar) as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    return cfg, defaults_path


def derive_title(video_path: pathlib.Path) -> str:
    stem = video_path.stem
    return " ".join(w.capitalize() for w in stem.replace("_", " ").replace("-", " ").split())


# Stopwords excluded from auto-tag generation.
_STOP = {"a","an","the","of","to","in","on","at","for","and","or","is","it","be",
         "this","that","with","by","from","as","but","not","are","was","were","i",
         "you","my","your","our","we","they","he","she","his","her","their","its"}


def derive_description(video_path: pathlib.Path, title: str) -> str:
    """Build a default description when user provides none.

    Filename "react-rerenders.mp4" → title "React Rerenders" →
        \"React Rerenders\\n\\n#ReactRerenders #React #Rerenders\"

    For per-video custom descriptions, drop a sidecar YAML next to the video.
    """
    words = [w for w in re.split(r"\s+", title) if w]
    if not words:
        return title
    pascal = "".join(w.capitalize() for w in words)
    word_tags = [f"#{w.capitalize()}" for w in words if w.lower() not in _STOP and len(w) > 2]
    tag_line = " ".join([f"#{pascal}"] + word_tags)
    return f"{title}\n\n{tag_line}"


def derive_tags(title: str) -> list:
    """Split title into tag list (no #), drop stopwords + short words."""
    words = [w for w in re.split(r"\s+", title) if w]
    return [w.lower() for w in words if w.lower() not in _STOP and len(w) > 2]


def click_button_by_text(text: str) -> bool:
    """Click via JS to bypass ref staleness. Returns True if found."""
    js = (
        "(()=>{const b=Array.from(document.querySelectorAll('ytcp-button,button'))"
        f".find(e=>(e.innerText||'').trim()===\"{text}\");"
        "if(b){b.scrollIntoView();b.click();return 'clicked';}return 'no';})()"
    )
    return "clicked" in ab("eval", js)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=pathlib.Path)
    ap.add_argument("--config", type=pathlib.Path, default=None)
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.is_file():
        sys.exit(f"[upload-one] not a file: {video}")
        return 66

    cfg, cfg_path = load_config(video, args.config)
    title = cfg.get("title") or derive_title(video)
    description = (cfg.get("description") or "").strip() or derive_description(video, title)
    if not (cfg.get("tags") or []):
        cfg["tags"] = derive_tags(title)
    visibility = cfg.get("visibility") or "public"
    schedule = cfg.get("schedule")
    if schedule and visibility == "public":
        visibility = "private"  # Studio rule: scheduled videos start private

    print(f"[upload-one] video={video.name} title={title!r} visibility={visibility} cfg={cfg_path}")

    # 1. Open upload dialog
    ab("open", "https://www.youtube.com/upload")
    time.sleep(7)
    url = ab("get", "url")
    if "accounts.google.com" in url:
        sys.exit(75)

    # 2. Check file input is present (fail-fast precondition)
    cnt = ab("eval", "document.querySelectorAll('input[type=file]').length").strip()
    if cnt != "1":
        # Try once more with a longer wait
        time.sleep(5)
        cnt = ab("eval", "document.querySelectorAll('input[type=file]').length").strip()
        if cnt != "1":
            print(f"[upload-one] file input not present (count={cnt})", file=sys.stderr)
            sys.exit(71)

    # 3. Attach file
    ab("upload", "input[type=file]", str(video))

    # 4. Wait for Details tab
    deadline = time.time() + 30
    title_ref = None
    while time.time() < deadline:
        s = snap()
        title_ref = find_ref(s, "Add a title that describes your video", role="textbox")
        if title_ref:
            break
        # Check for daily-limit error mid-render
        if "Daily upload limit" in s:
            print("[upload-one] YouTube rate limit", file=sys.stderr)
            sys.exit(77)
        time.sleep(2)
    if not title_ref:
        print("[upload-one] Details tab never rendered", file=sys.stderr)
        sys.exit(71)

    # 5. Title — overwrite if config sets one different from auto-fill
    s = snap()
    title_ref = find_ref(s, "Add a title that describes your video", role="textbox")
    if title_ref and cfg.get("title"):
        click(title_ref); ab("press", "Meta+A"); ab("press", "Delete")
        fill(title_ref, title)

    # 6. Description
    if description:
        s = snap()
        desc_ref = find_ref(s, "Tell viewers about your video", role="textbox")
        if desc_ref:
            click(desc_ref); fill(desc_ref, description)

    # 7. Made-for-kids (required)
    s = snap()
    kids_label = ("Yes, it's made for kids" if cfg.get("made_for_kids")
                  else "No, it's not made for kids")
    ref = find_ref(s, kids_label, role="radio")
    if ref: click(ref)

    # 8. Show advanced settings — DOM rebuilds, refs invalidated
    click_button_by_text("Show more")
    time.sleep(2)

    # 9. Re-confirm kids choice (selection often lost on rebuild)
    s = snap()
    ref = find_ref(s, kids_label, role="radio")
    if ref: click(ref)

    # 10. Altered content (required)
    alt_label = ("Yes, it includes altered content" if cfg.get("altered_content")
                 else "No, it doesn’t include altered content")
    ref = find_ref(s, alt_label, role="radio")
    if ref: click(ref)

    # 11. Tags
    tags = cfg.get("tags") or []
    if tags:
        s = snap()
        tags_ref = find_ref(s, "Tags", role="textbox")
        if tags_ref:
            click(tags_ref); fill(tags_ref, ", ".join(tags))

    # 12. Paid promotion
    if cfg.get("paid_promotion"):
        s = snap()
        ref = find_ref(s, "My video contains paid promotion", role="checkbox")
        if ref: click(ref)

    # 13. Boolean checkboxes — toggle ONLY if user override differs from Studio default.
    # All these are checked=true by default in Studio; overlay sets them to false → toggle.
    bool_overrides = {
        "automatic_chapters": ("Allow automatic chapters and key moments", True),
        "automatic_places":   ("Allow automatic places",                   True),
        "automatic_concepts": ("Allow automatic concepts",                 True),
        "allow_embedding":    ("Allow embedding",                          True),
        "notify_subscribers": ("Publish to subscriptions feed and notify subscribers", True),
        "show_likes":         ("Show how many viewers like this video",    True),
    }
    for key, (label, default) in bool_overrides.items():
        if key not in cfg or cfg[key] is None:
            continue
        if cfg[key] != default:
            s = snap()
            ref = find_ref(s, label, role="checkbox")
            if ref: click(ref)

    # 14. Advance Details → Video elements → Checks → Visibility
    for _ in range(3):
        ab("find", "role", "button", "click", "--name", "Next")
        time.sleep(3)

    # 15. Visibility radio
    vis_label = {"private": "Private", "unlisted": "Unlisted", "public": "Public"}[visibility]
    s = snap()
    ref = find_ref(s, vis_label, role="radio")
    if not ref:
        print(f"[upload-one] visibility radio '{vis_label}' not found", file=sys.stderr)
        sys.exit(71)
    click(ref)
    time.sleep(1)

    # 16. Schedule (private + future date)
    if schedule:
        # Best-effort: open schedule expander, type date+time. Studio's schedule
        # widget is a custom dropdown — leave a TODO for proper interaction.
        click_button_by_text("Schedule")
        time.sleep(2)
        # Format expected by Studio: usually a date picker, not free text. For
        # now, log and skip — user can edit in Studio after upload.
        print(f"[upload-one] WARNING: schedule={schedule} requested but widget interaction "
              "not yet implemented — video saved as Private; set the date manually in Studio",
              file=sys.stderr)

    # 17. Save / Publish (button name varies by Studio version)
    saved = False
    for label in ("Save", "Publish"):
        try:
            r = subprocess.run(
                ["agent-browser", "--auto-connect", "find", "role", "button",
                 "click", "--name", label],
                capture_output=True, text=True, timeout=15,
            )
            if r.returncode == 0:
                saved = True
                break
        except subprocess.TimeoutExpired:
            continue
    if not saved:
        print("[upload-one] Save/Publish button not found", file=sys.stderr)
        sys.exit(71)
    time.sleep(5)

    # 18. Extract URL from confirmation dialog
    # Studio confirmation dialog can show youtu.be (long-form), watch?v= (long-form),
    # or youtube.com/shorts/<id> (vertical 9:16 auto-classified as Short).
    # Regular videos: dialog snapshot has the URL. Shorts: snapshot may not have it,
    # so also probe for Studio's "/shorts/<id>" anchor on the channel page.
    s = ab("snapshot")
    m = (re.search(r"https://(?:www\.)?youtube\.com/shorts/[A-Za-z0-9_-]+", s)
         or re.search(r"https://youtu\.be/[A-Za-z0-9_-]+", s)
         or re.search(r"https://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]+", s))
    if not m:
        # Fallback: ask the page for any shorts/watch href (handles Save-button
        # dialog that just closes without surfacing the URL inline).
        href = ab("eval",
                  "(()=>{const a=document.querySelector('a[href*=\"/shorts/\"],"
                  "a[href*=\"youtu.be/\"],a[href*=\"watch?v=\"]'); return a?a.href:'';})()")
        href = href.strip().strip('"')
        if href:
            m = re.search(r"https?://[^\s\"']+", href)
    if not m:
        print("[upload-one] published but no URL extracted from confirmation dialog", file=sys.stderr)
        sys.exit(71)
    video_url = m.group(0)

    # 19. Close confirmation
    subprocess.run(["agent-browser", "--auto-connect", "find", "role", "button",
                    "click", "--name", "Close"], capture_output=True)

    # 20. Delete source + sidecars; record in posted.log
    project = video.parent.parent
    posted_log = project / "videos" / "posted.log"
    posted_log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(posted_log, "a") as f:
        f.write(f"{ts}\t{video.name}\t{video_url}\n")

    for sidecar_ext in (".yaml", ".jpg", ".png"):
        s = video.with_suffix(sidecar_ext)
        if s.exists():
            s.unlink()
    video.unlink()

    print(video_url)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
