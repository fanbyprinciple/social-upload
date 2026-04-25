#!/usr/bin/env python3
"""upload-one.py <video-path> [--config defaults.yaml]

Upload one video to TikTok. Two backends:
  - api      → TikTok Content Posting API (needs tiktok-api-creds.yaml)
  - browser  → drives studio.tiktok.com/upload via agent-browser
  - auto     → try api, fall back to browser on credential or API error

Mode is read from upload-defaults.yaml `mode:` (default `auto`).

Exit codes:
  0   uploaded; URL printed to stdout
  64  usage
  66  video file missing
  70  prereq missing (yaml, requests, agent-browser, etc.)
  71  composer/API interaction failed mid-flow
  72  posted but URL not extracted (browser path)
  75  session/oauth expired
  77  TikTok soft-block / rate limit
  78  account state wrong
"""

import argparse, json, re, sys, time, subprocess, pathlib, datetime, urllib.request, urllib.parse, urllib.error

try:
    import yaml
except ImportError:
    sys.exit("[tt upload-one] pip install --break-system-packages pyyaml")


# Browser-mode selectors (placeholder — verify on first live run).
SELECTORS = {
    "modal_or_page":            "Upload",
    "select_button":            "Select video",
    "caption_textbox":          "Caption",
    "post_button":              "Post",
    "share_complete_text":      "Your video has been uploaded",
    "soft_block_text":          "Try again later",
    "rate_limit_text":          "Daily limit",
    "copyright_warning_text":   "Copyright",
    "guidelines_block_text":    "violates our community guidelines",
}


def ab(*args, capture=True, timeout=60):
    r = subprocess.run(["agent-browser", "--auto-connect", *args],
                       capture_output=capture, text=True, timeout=timeout)
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
            pathlib.Path.home() / "codeplay/ijp_research/CSOS/socials/tiktok-uploads/upload-defaults.yaml",
        ]
        defaults_path = next((c for c in candidates if c.exists()), None)
    if not defaults_path or not defaults_path.exists():
        sys.exit("[tt upload-one] no upload-defaults.yaml found")
    with open(defaults_path) as f:
        cfg = yaml.safe_load(f) or {}
    sidecar = video_path.with_suffix(".yaml")
    if sidecar.exists():
        with open(sidecar) as f:
            cfg = deep_merge(cfg, yaml.safe_load(f) or {})
    return cfg, defaults_path


def load_api_creds(project: pathlib.Path):
    p = project / "tiktok-api-creds.yaml"
    if not p.exists(): return None
    with open(p) as f:
        c = yaml.safe_load(f) or {}
    if not all(c.get(k) for k in ("client_key", "client_secret", "access_token")):
        return None
    return c


_STOP = {"a","an","the","of","to","in","on","at","for","and","or","is","it","be",
         "this","that","with","by","from","as","but","not","are","was","were","i",
         "you","my","your","our","we","they","he","she","his","her","their","its"}


def derive_caption(video_path: pathlib.Path) -> str:
    stem = video_path.stem.replace("_", " ").replace("-", " ").strip()
    words = [w for w in re.split(r"\s+", stem) if w]
    if not words: return "New video\n\n#fyp"
    title_case = " ".join(w.capitalize() for w in words).rstrip(".") + "."
    pascal = "".join(w.capitalize() for w in words)
    word_tags = [f"#{w.lower()}" for w in words if w.lower() not in _STOP and len(w) > 2]
    tag_line = " ".join([f"#{pascal}"] + word_tags + ["#fyp", "#foryou"])
    return f"{title_case}\n\n{tag_line}"


# ───────────────────── API path ─────────────────────

def api_upload(video: pathlib.Path, cfg: dict, creds: dict) -> str:
    """Post via TikTok Content Posting API.

    Endpoint differs by mode: `inbox` (auto-approved Sandbox; user manually
    publishes from drafts) vs `direct` (Production; requires TikTok audit).
    Returns a URL/identifier; for inbox mode the "URL" is the TikTok studio
    drafts page since the actual post ID isn't available until the user
    publishes.
    """
    mode = creds.get("endpoint_mode", "inbox")
    base = "https://open.tiktokapis.com/v2"
    init_url = (f"{base}/post/publish/inbox/video/init/" if mode == "inbox"
                else f"{base}/post/publish/video/init/")

    # 1. Init the upload, get upload_url + publish_id
    payload = {"source_info": {"source": "FILE_UPLOAD",
                                "video_size": video.stat().st_size,
                                "chunk_size": video.stat().st_size,
                                "total_chunk_count": 1}}
    if mode != "inbox":
        payload["post_info"] = {
            "title": cfg.get("caption", ""),
            "privacy_level": {"public": "PUBLIC_TO_EVERYONE",
                               "friends": "MUTUAL_FOLLOW_FRIENDS",
                               "private": "SELF_ONLY"}.get(cfg.get("visibility", "public"), "PUBLIC_TO_EVERYONE"),
            "disable_duet": not cfg.get("allow_duet", True),
            "disable_comment": not cfg.get("allow_comments", True),
            "disable_stitch": not cfg.get("allow_stitch", True),
            "video_cover_timestamp_ms": int((cfg.get("cover_frame_seconds") or 0) * 1000),
        }

    req = urllib.request.Request(
        init_url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {creds['access_token']}",
                 "Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    try:
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        if e.code in (401, 403):
            print(f"[tt api] auth failed: {body}", file=sys.stderr); sys.exit(75)
        if e.code == 429:
            print(f"[tt api] rate limit: {body}", file=sys.stderr); sys.exit(77)
        print(f"[tt api] init failed {e.code}: {body}", file=sys.stderr); sys.exit(71)

    if (resp.get("error", {}) or {}).get("code") not in (None, "ok"):
        print(f"[tt api] init err: {resp['error']}", file=sys.stderr); sys.exit(71)
    data = resp.get("data", {})
    upload_url = data.get("upload_url")
    publish_id = data.get("publish_id")
    if not upload_url:
        print(f"[tt api] no upload_url in init response: {resp}", file=sys.stderr); sys.exit(71)

    # 2. PUT the video bytes to the upload_url
    size = video.stat().st_size
    with open(video, "rb") as fh:
        put_req = urllib.request.Request(
            upload_url, data=fh.read(),
            headers={"Content-Type": "video/mp4",
                     "Content-Range": f"bytes 0-{size - 1}/{size}"},
            method="PUT",
        )
        urllib.request.urlopen(put_req, timeout=300)

    # 3. Poll status until PUBLISH_COMPLETE / SEND_TO_USER_INBOX
    status_url = f"{base}/post/publish/status/fetch/"
    deadline = time.time() + 300
    final = None
    while time.time() < deadline:
        sreq = urllib.request.Request(
            status_url,
            data=json.dumps({"publish_id": publish_id}).encode(),
            headers={"Authorization": f"Bearer {creds['access_token']}",
                     "Content-Type": "application/json; charset=UTF-8"},
            method="POST",
        )
        sresp = json.loads(urllib.request.urlopen(sreq, timeout=30).read())
        status = (sresp.get("data") or {}).get("status", "")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            final = sresp; break
        if status.startswith("FAILED"):
            print(f"[tt api] publish failed: {sresp}", file=sys.stderr); sys.exit(71)
        time.sleep(5)

    if not final:
        print("[tt api] publish never completed within 5 min", file=sys.stderr); sys.exit(71)

    # 4. Build URL — direct mode returns publish_url; inbox returns drafts pointer
    publicaly_available_post_id = (final.get("data") or {}).get("publicaly_available_post_id")
    if publicaly_available_post_id and isinstance(publicaly_available_post_id, list):
        return f"https://www.tiktok.com/@me/video/{publicaly_available_post_id[0]}"
    return "https://www.tiktok.com/inbox  (draft — open TikTok app to publish)"


# ───────────────────── Browser path ─────────────────────

def browser_upload(video: pathlib.Path, cfg: dict) -> str:
    """Drive studio.tiktok.com/upload. SELECTORS need live verification on
    first run; this is the structural skeleton."""
    ab("open", "https://studio.tiktok.com/upload")
    time.sleep(8)

    if page_has_text(SELECTORS["soft_block_text"]) \
       or page_has_text(SELECTORS["rate_limit_text"]):
        sys.exit(77)
    if "/login" in ab("get", "url"):
        sys.exit(75)

    # Find file input. Studio's upload page typically has 1 input[type=file].
    cnt = ab("eval", "document.querySelectorAll('input[type=file]').length").strip()
    if cnt == "0":
        time.sleep(5)
        cnt = ab("eval", "document.querySelectorAll('input[type=file]').length").strip()
        if cnt == "0":
            print("[tt browser] file input not present", file=sys.stderr); sys.exit(71)

    ab("upload", "input[type=file]", str(video))
    time.sleep(20)  # upload + processing

    # Caption
    s = snap()
    cap_ref = find_ref(s, SELECTORS["caption_textbox"], role="textbox")
    if cap_ref:
        click(cap_ref); fill(cap_ref, cfg.get("caption") or derive_caption(video))

    # Visibility / engagement toggles — TODO live: capture exact labels then map
    # cfg.visibility, cfg.allow_comments, cfg.allow_duet, cfg.allow_stitch,
    # cfg.ai_generated, cfg.audience_age_18plus, cfg.schedule.

    # Copyright pre-check warning
    if page_has_text(SELECTORS["copyright_warning_text"]) \
       and not cfg.get("copyright_check_skip"):
        print("[tt browser] copyright warning — set copyright_check_skip: true to override",
              file=sys.stderr); sys.exit(71)

    # Click Post
    if not click_button_by_text(SELECTORS["post_button"]):
        print("[tt browser] Post button not found", file=sys.stderr); sys.exit(71)

    # Wait for completion
    deadline = time.time() + 180
    while time.time() < deadline:
        if page_has_text(SELECTORS["share_complete_text"]): break
        if page_has_text(SELECTORS["soft_block_text"]): sys.exit(77)
        if page_has_text(SELECTORS["guidelines_block_text"]):
            print("[tt browser] community guidelines block", file=sys.stderr); sys.exit(71)
        time.sleep(3)
    else:
        print("[tt browser] no completion within 3 min", file=sys.stderr); sys.exit(72)

    # Extract URL — TikTok URL pattern: /@<handle>/video/<id>
    href = ab("eval",
              "(()=>{const a=document.querySelector('a[href*=\"/video/\"]');"
              "return a?a.href:'';})()").strip().strip('"')
    m = re.search(r"https?://[^\s\"']*tiktok\.com/@[^/]+/video/\d+", href)
    if m: return m.group(0)
    print("[tt browser] published but URL not extracted", file=sys.stderr); sys.exit(72)


# ───────────────────── Main ─────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=pathlib.Path)
    ap.add_argument("--config", type=pathlib.Path, default=None)
    ap.add_argument("--mode", choices=["api", "browser", "auto"], default=None,
                    help="override the mode field in upload-defaults.yaml")
    args = ap.parse_args()

    video = args.video.resolve()
    if not video.is_file():
        print(f"[tt upload-one] not a file: {video}", file=sys.stderr); sys.exit(66)

    cfg, cfg_path = load_config(video, args.config)
    mode = args.mode or cfg.get("mode") or "auto"
    project = video.parent.parent
    creds = load_api_creds(project)

    print(f"[tt upload-one] video={video.name} mode={mode} cfg={cfg_path}")

    url = None
    if mode in ("api", "auto") and creds:
        try:
            url = api_upload(video, cfg, creds)
            print(f"[tt upload-one] api success", file=sys.stderr)
        except SystemExit:
            if mode == "api": raise
            print("[tt upload-one] api failed; falling back to browser", file=sys.stderr)

    if not url:
        url = browser_upload(video, cfg)

    # Delete source + sidecars; record posted.log
    posted_log = project / "videos" / "posted.log"
    posted_log.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    with open(posted_log, "a") as f:
        f.write(f"{ts}\t{video.name}\t{url}\n")
    for ext in (".yaml", ".jpg", ".png"):
        sc = video.with_suffix(ext)
        if sc.exists(): sc.unlink()
    video.unlink()

    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
