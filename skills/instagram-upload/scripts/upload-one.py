#!/usr/bin/env python3
"""upload-one.py <video-path> [--config defaults.yaml]

Upload one Reel to Instagram via instagram.com's web composer driven by
agent-browser. Reads YAML config (defaults overlaid by per-video sidecar),
performs the verified composer sequence, deletes source on success, returns
the Reel URL.

Verified working sequence (running.rahul.25, 2026-04-25):
  home → sidebar "New post" → "Post" submenu → modal "Create new post"
  → upload to input[type=file][accept*="video"]
  → Crop page (Next) → Edit page (Next) → New reel page (caption, Share)
  → "Reel shared" dialog → grab a[href*="/reel/"]

Exit codes:
  0  uploaded; URL printed to stdout
  64 usage error
  66 video file missing
  70 prereq missing
  71 IG composer interaction failed mid-flow
  72 published but URL not extracted
  75 session expired or 2FA challenge
  77 IG soft-block ("We limit how often" / "We restrict certain activity")
  78 account state wrong (e.g. personal account, only images allowed)
"""

import argparse, re, sys, time, subprocess, pathlib, datetime

try:
    import yaml
except ImportError:
    sys.exit("[ig upload-one] pip install --break-system-packages pyyaml")


# Verified selectors. Update references/selectors.md when IG changes labels.
SELECTORS = {
    "sidebar_new_post":       "New post",
    "post_menu_item":         "Post",
    "modal_heading":          "Create new post",
    "select_from_computer":   "Select From Computer",
    "crop_heading":           "Crop",
    "edit_heading":           "Edit",
    "new_reel_heading":       "New reel",
    "caption_textbox":        "Write a caption",
    "location_textbox":       "Add Location",
    "advanced_settings":      "Advanced Settings",
    "share_button":           "Share",
    "share_complete_text":    "Your reel has been shared",
    "image_only_error":       "Only images can be posted",
    "soft_block_text":        "We limit how often",
    "restrict_block_text":    "We restrict certain activity",
    "guidelines_block_text":  "goes against our community guidelines",
}


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
        if label_l not in ll: continue
        if role_l and role_l not in ll: continue
        m = re.search(r"ref=(e\d+)", line)
        if m: return f"@{m.group(1)}"
    return None


def click(ref): ab("click", ref)
def fill(ref, text): ab("fill", ref, text)


def click_button_by_text(text: str) -> bool:
    js = (
        "(()=>{const b=Array.from(document.querySelectorAll('button,div[role=\"button\"],a'))"
        f".find(e=>(e.innerText||'').trim()===\"{text}\");"
        "if(b){b.scrollIntoView();b.click();return 'clicked';}return 'no';})()"
    )
    return "clicked" in ab("eval", js)


def page_has_text(text: str) -> bool:
    return "yes" in ab("eval", f"(document.body.innerText||'').includes(\"{text}\")?'yes':'no'")


def wait_for_text(text: str, timeout: int = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if page_has_text(text): return True
        time.sleep(2)
    return False


def detect_blockers() -> int | None:
    """Return exit code if a fatal blocker is on screen, else None."""
    if page_has_text(SELECTORS["soft_block_text"]) \
       or page_has_text(SELECTORS["restrict_block_text"]):
        return 77
    if page_has_text(SELECTORS["guidelines_block_text"]):
        return 71
    if page_has_text(SELECTORS["image_only_error"]):
        return 78
    url = ab("get", "url")
    if "/accounts/login" in url or "/challenge" in url:
        return 75
    return None


def deep_merge(base, overlay):
    if not isinstance(overlay, dict): return overlay
    out = dict(base) if isinstance(base, dict) else {}
    for k, v in overlay.items():
        out[k] = deep_merge(out.get(k), v) if isinstance(v, dict) else v
    return out


def load_config(video_path: pathlib.Path, explicit_config: pathlib.Path | None):
    if explicit_config:
        defaults_path = explicit_config
    else:
        candidates = [
            video_path.parent.parent / "upload-defaults.yaml",
            pathlib.Path.cwd() / "upload-defaults.yaml",
            pathlib.Path.home() / "codeplay/ijp_research/CSOS/socials/instagram-reels/upload-defaults.yaml",
        ]
        defaults_path = next((c for c in candidates if c.exists()), None)
    if not defaults_path or not defaults_path.exists():
        sys.exit("[ig upload-one] no upload-defaults.yaml found")
    with open(defaults_path) as f:
        cfg = yaml.safe_load(f) or {}
    sidecar = video_path.with_suffix(".yaml")
    if sidecar.exists():
        with open(sidecar) as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    return cfg, defaults_path


# Stopwords excluded from auto-hashtag generation.
_STOP = {"a","an","the","of","to","in","on","at","for","and","or","is","it","be",
         "this","that","with","by","from","as","but","not","are","was","were","i",
         "you","my","your","our","we","they","he","she","his","her","their","its"}


def derive_caption(video_path: pathlib.Path) -> str:
    """Build a default caption from filename when user provides none.

    Filename "Journey begins.mp4" → \"Journey begins.\\n\\n#JourneyBegins #Journey #Begins #Reels\"

    Smarter visual-aware captions need an LLM call (out of scope — user's
    domain). For per-video custom captions, drop a sidecar YAML with `caption:`
    next to the video.
    """
    stem = video_path.stem.replace("_", " ").replace("-", " ").strip()
    words = [w for w in re.split(r"\s+", stem) if w]
    if not words:
        return "New reel\n\n#Reels"
    title_case = " ".join(w.capitalize() for w in words).rstrip(".") + "."
    pascal = "".join(w.capitalize() for w in words)
    word_tags = [f"#{w.capitalize()}" for w in words if w.lower() not in _STOP and len(w) > 2]
    tag_line = " ".join([f"#{pascal}"] + word_tags + ["#Reels"])
    return f"{title_case}\n\n{tag_line}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=pathlib.Path)
    ap.add_argument("--config", type=pathlib.Path, default=None)
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.is_file():
        print(f"[ig upload-one] not a file: {video}", file=sys.stderr); sys.exit(66)

    cfg, cfg_path = load_config(video, args.config)
    # Filename auto-derivation disabled: caption MUST come from the YAML
    # sidecar (or upload-defaults.yaml). The producing pipeline (e.g. Moto Razr)
    # is the source of truth for content metadata.
    caption = (cfg.get("caption") or "").strip()
    if not caption:
        sys.exit("[ig upload-one] missing 'caption' in resolved YAML — sidecar must provide it (auto-derive disabled)")
    location = cfg.get("location") or ""
    hide_likes = bool(cfg.get("hide_like_count"))
    disable_comments = bool(cfg.get("disable_comments"))
    crosspost = cfg.get("crosspost_to_facebook", True)

    print(f"[ig upload-one] video={video.name} caption={caption[:60]!r}... cfg={cfg_path}")

    # 1. Open IG home (if not already there)
    ab("open", "https://www.instagram.com/")
    time.sleep(6)
    if (rc := detect_blockers()) is not None: sys.exit(rc)

    # 2. Sidebar "New post"
    s = snap()
    new_post_ref = find_ref(s, SELECTORS["sidebar_new_post"], role="link")
    if new_post_ref:
        click(new_post_ref)
    else:
        click_button_by_text(SELECTORS["sidebar_new_post"])
    time.sleep(2)

    # 3. "Post" submenu
    if not click_button_by_text(SELECTORS["post_menu_item"]):
        ab("find", "text", SELECTORS["post_menu_item"], "click")
    time.sleep(3)

    # 4. Wait for modal
    if not wait_for_text(SELECTORS["modal_heading"], timeout=10):
        print("[ig upload-one] 'Create new post' modal didn't appear", file=sys.stderr)
        sys.exit(71)

    # 5. Upload via the video-accepting input. IG composer has 3 input[type=file]
    # elements; only the third (in the modal) accepts video.
    n = ab("eval", "document.querySelectorAll('input[type=file][accept*=\"video\"]').length").strip()
    if n != "1":
        print(f"[ig upload-one] expected 1 video input, found {n}", file=sys.stderr)
        sys.exit(71)
    ab("upload", 'input[type=file][accept*="video"]', str(video))

    # 6. Wait for Crop page
    if not wait_for_text(SELECTORS["crop_heading"], timeout=45):
        if (rc := detect_blockers()) is not None: sys.exit(rc)
        print("[ig upload-one] Crop page never appeared", file=sys.stderr); sys.exit(71)
    if not click_button_by_text("Next"):
        print("[ig upload-one] Crop Next not clickable", file=sys.stderr); sys.exit(71)

    # 7. Wait for Edit page → Next
    if not wait_for_text(SELECTORS["edit_heading"], timeout=20):
        print("[ig upload-one] Edit page never appeared", file=sys.stderr); sys.exit(71)
    if not click_button_by_text("Next"):
        print("[ig upload-one] Edit Next not clickable", file=sys.stderr); sys.exit(71)

    # 8. New reel page — fill caption
    if not wait_for_text(SELECTORS["new_reel_heading"], timeout=15):
        print("[ig upload-one] New reel page never appeared", file=sys.stderr); sys.exit(71)
    s = snap()
    cap_ref = find_ref(s, SELECTORS["caption_textbox"], role="textbox")
    if cap_ref:
        click(cap_ref); fill(cap_ref, caption)

    # 9. Optional location
    if location:
        s = snap()
        loc_ref = find_ref(s, SELECTORS["location_textbox"], role="textbox")
        if loc_ref:
            click(loc_ref); fill(loc_ref, location)
            time.sleep(1)
            ab("eval",
               "(()=>{const o=document.querySelector('[role=\"button\"][tabindex=\"0\"]');"
               "if(o)o.click();})()")

    # 10. Advanced settings — open + toggle the off-from-default checkboxes.
    if hide_likes or disable_comments or not crosspost:
        click_button_by_text(SELECTORS["advanced_settings"])
        time.sleep(2)
        s = snap()
        if hide_likes:
            ref = find_ref(s, "Hide like and view counts") \
                  or find_ref(s, "Hide like count")
            if ref: click(ref)
        if disable_comments:
            ref = find_ref(s, "Turn off commenting")
            if ref: click(ref)
        if not crosspost:
            ref = find_ref(s, "Also share to Facebook") \
                  or find_ref(s, "Recommend on Facebook")
            if ref: click(ref)

    # 11. Share
    if (rc := detect_blockers()) is not None: sys.exit(rc)
    if not click_button_by_text(SELECTORS["share_button"]):
        print("[ig upload-one] Share button not clickable", file=sys.stderr); sys.exit(71)

    # 12. Wait for "Your reel has been shared" — IG sometimes takes 30-90 sec.
    deadline = time.time() + 120
    shared = False
    while time.time() < deadline:
        if (rc := detect_blockers()) is not None: sys.exit(rc)
        if page_has_text(SELECTORS["share_complete_text"]):
            shared = True
            break
        time.sleep(3)
    if not shared:
        print("[ig upload-one] no 'Reel shared' confirmation within 120s", file=sys.stderr)
        sys.exit(72)

    # 13. Extract URL — first try the dialog's anchor, fall back to profile poll.
    href = ab("eval",
              "(()=>{const a=document.querySelector('a[href*=\"/reel/\"]');"
              "return a?a.href:'';})()")
    href = href.strip().strip('"')
    m = re.search(r"https?://[^\s\"']+/reel/[A-Za-z0-9_-]+/?", href) if href else None
    reel_url = m.group(0) if m else ""

    if not reel_url:
        # Fallback: hop to profile reels page and grab newest /reel/ link.
        handle_js = ("(()=>{const a=document.querySelector('a[href^=\"/\"][href$=\"/\"]'); "
                     "return a?a.getAttribute('href').replace(/^\\//,'').replace(/\\/$/,''):'';})()")
        handle = ab("eval", handle_js).strip().strip('"').split('/')[0]
        if handle:
            ab("open", f"https://www.instagram.com/{handle}/reels/")
            time.sleep(5)
            href = ab("eval",
                      "(()=>{const a=document.querySelector('a[href*=\"/reel/\"]');"
                      "return a?a.href:'';})()").strip().strip('"')
            m = re.search(r"https?://[^\s\"']+/reel/[A-Za-z0-9_-]+/?", href)
            if m: reel_url = m.group(0)

    if not reel_url:
        pending = video.with_suffix(video.suffix + ".pending")
        pending.write_text("URL pending — re-poll profile reels grid next run\n")
        print("[ig upload-one] published but URL not extracted", file=sys.stderr); sys.exit(72)

    # 14. Delete source + sidecars; record in posted.log
    project = video.parent.parent
    posted_log = project / "videos" / "posted.log"
    posted_log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(posted_log, "a") as f:
        f.write(f"{ts}\t{video.name}\t{reel_url}\n")
    for ext in (".yaml", ".jpg", ".png", ".pending"):
        sc = video.with_suffix(ext)
        if sc.exists(): sc.unlink()
    video.unlink()

    print(reel_url)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
