"""
YouTube Live Stream Recorder -- Audited Production Engine
Optimized for GitHub Actions 14GB Ubuntu Runners
- Dual Probe Live Detection (RSS Feed + Channel Live HTML)
- Disk-Safe Streaming & Direct TS Binary Append
- Official Gofile (upload.gofile.io) + Pixeldrain Fallback
- Telegram Notification Engine & Instant Cleanup
"""

import atexit
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime

# =============================================================================
# ENVIRONMENT & CONFIGURATION
# =============================================================================

CHANNEL_HANDLE = os.getenv("CHANNEL_HANDLE", "@bekalki").strip()
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID", "").strip()
HOURS = float(os.getenv("HOURS", "5.3"))
OUT_DIR = os.getenv("OUT_DIR", "./streams")
COOKIE_FILE = os.getenv("COOKIE_FILE", "cookies.txt")
USE_COOKIES = os.getenv("USE_COOKIES", "false").lower() == "true"

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "").strip()

CHECK_INTERVAL_SECONDS = 20
HEARTBEAT_SECONDS = 15
STALL_TIMEOUT_SECONDS = 180
MIN_VALID_SIZE_BYTES = 1_500_000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

os.makedirs(OUT_DIR, exist_ok=True)

def slug(val):
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", val).strip("_")
    return clean.lower()

CHANNEL_SLUG = slug(CHANNEL_HANDLE)
LOG_FILE = os.path.join(OUT_DIR, f"{CHANNEL_SLUG}_recorder.log")

# =============================================================================
# LOGGING UTILITIES
# =============================================================================

def log(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

def format_hms(seconds):
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

# =============================================================================
# DEPENDENCY BOOTSTRAPPER
# =============================================================================

def ensure_dependencies():
    try:
        import yt_dlp
    except ImportError:
        log(f"installing dependencies for {CHANNEL_HANDLE}")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-U", "yt-dlp", "requests"],
            check=True
        )

ensure_dependencies()
import yt_dlp

# =============================================================================
# CHANNEL IDENTITY RESOLUTION
# =============================================================================

HAS_COOKIES = USE_COOKIES and os.path.isfile(COOKIE_FILE) and os.path.getsize(COOKIE_FILE) > 0

def resolve_channel_id():
    global TARGET_CHANNEL_ID
    if TARGET_CHANNEL_ID and TARGET_CHANNEL_ID.startswith("UC"):
        return TARGET_CHANNEL_ID
    
    url = f"https://www.youtube.com/{CHANNEL_HANDLE}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r'\"channelId\":\"(UC[a-zA-Z0-9_-]{22})\"', html)
            if m:
                TARGET_CHANNEL_ID = m.group(1)
                return TARGET_CHANNEL_ID
            m = re.search(r'<meta itemprop=\"channelId\" content=\"(UC[a-zA-Z0-9_-]{22})\">', html)
            if m:
                TARGET_CHANNEL_ID = m.group(1)
                return TARGET_CHANNEL_ID
    except Exception:
        pass
    return TARGET_CHANNEL_ID

TARGET_CHANNEL_ID = resolve_channel_id()
log(f"target_identity | channel_id={TARGET_CHANNEL_ID} | cookies={HAS_COOKIES}")
log(f"started | channel={CHANNEL_HANDLE} | duration={HOURS}h | disk_safe_merge=on | single_upload_path=on")

# =============================================================================
# LIVE PROBE ENGINE
# =============================================================================

def probe_rss():
    if not TARGET_CHANNEL_ID:
        return None
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={TARGET_CHANNEL_ID}"
    try:
        req = urllib.request.Request(rss_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_text = resp.read().decode("utf-8", errors="ignore")
            video_ids = re.findall(r"<yt:videoId>([a-zA-Z0-9_-]{11})</yt:videoId>", xml_text)
            for vid in video_ids[:3]:
                v_url = f"https://www.youtube.com/watch?v={vid}"
                v_req = urllib.request.Request(v_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(v_req, timeout=8) as v_resp:
                    v_html = v_resp.read().decode("utf-8", errors="ignore")
                    if '"isLive":true' in v_html or '"isLiveNow":true' in v_html:
                        return vid, "rss_feed"
    except Exception:
        pass
    return None

def probe_channel_page():
    url = f"https://www.youtube.com/{CHANNEL_HANDLE}/live"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            if '"isLive":true' in html or '"isLiveNow":true' in html:
                m = re.search(r'\"liveStreamabilityRenderer\":{\"videoId\":\"([a-zA-Z0-9_-]{11})\"', html)
                if not m:
                    m = re.search(r'href=\"/watch\?v=([a-zA-Z0-9_-]{11})\"', html)
                if m:
                    return m.group(1), "channel_live_page"
                return url, "channel_live_page"
    except Exception:
        pass
    return None

def detect_live():
    res = probe_rss()
    if res:
        vid, src = res
        log(f"detect live | source={src} | live id={vid} | verified=html")
        return vid, src
    
    res = probe_channel_page()
    if res:
        vid, src = res
        log(f"detect live | source={src} | target={vid}")
        return vid, src

    return None, None

# =============================================================================
# UPLOAD ENGINE (GOFILE + PIXELDRAIN + TELEGRAM)
# =============================================================================

def upload_and_cleanup(filepath):
    if not filepath or not os.path.isfile(filepath):
        return
    filename = os.path.basename(filepath)
    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    log(f"upload_starting | {filename} ({size_mb:.1f} MB)")

    gofile_link = ""
    pixeldrain_link = ""

    # 1. Gofile Global Endpoint
    for attempt in range(1, 3):
        try:
            up_res = subprocess.run(
                ["curl", "-4", "-s", "-F", f"file=@{filepath}", "https://upload.gofile.io/uploadfile"],
                capture_output=True, text=True, timeout=1800
            )
            if up_res.returncode == 0 and up_res.stdout.strip():
                data = json.loads(up_res.stdout)
                if data.get("status") == "ok":
                    gofile_link = data.get("data", {}).get("downloadPage", "")
                    if gofile_link:
                        break
        except Exception as exc:
            log(f"gofile_attempt_{attempt}_error | {exc}")
        time.sleep(3)

    # 2. Pixeldrain Fallback
    if not gofile_link:
        log("gofile_failed | trying Pixeldrain fallback...")
        try:
            pd_res = subprocess.run(
                ["curl", "-4", "-s", "-T", filepath, "https://pixeldrain.com/api/file/"],
                capture_output=True, text=True, timeout=1800
            )
            if pd_res.returncode == 0 and pd_res.stdout.strip():
                pd_id = json.loads(pd_res.stdout).get("id", "")
                if pd_id:
                    pixeldrain_link = f"https://pixeldrain.com/u/{pd_id}"
        except Exception as exc:
            log(f"pixeldrain_error | {exc}")

    print("==================================================", flush=True)
    print(f"Platform: YOUTUBE | Channel: {CHANNEL_HANDLE}", flush=True)
    print(f"File: {filename} ({size_mb:.1f} MB)", flush=True)
    if gofile_link:
        print(f"Download Link (Gofile): {gofile_link}", flush=True)
    if pixeldrain_link:
        print(f"Download Link (Pixeldrain): {pixeldrain_link}", flush=True)
    print("==================================================", flush=True)

    # 3. Telegram Notification
    if TG_TOKEN and TG_CHAT and (gofile_link or pixeldrain_link):
        msg = f"🔴 <b>[YouTube] {CHANNEL_HANDLE} Stream Recorded!</b>\n📂 <b>File:</b> <code>{filename}</code> ({size_mb:.1f} MB)"
        if gofile_link:
            msg += f"\n🔗 <b>Gofile:</b> {gofile_link}"
        if pixeldrain_link:
            msg += f"\n🛡️ <b>Pixeldrain:</b> {pixeldrain_link}"
        try:
            subprocess.run([
                "curl", "-4", "-s", "-X", "POST", f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
                "-d", f"chat_id={TG_CHAT}", "-d", "parse_mode=HTML", "-d", f"text={msg}"
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
        except Exception:
            pass

    # 4. Immediate Cleanup
    if gofile_link or pixeldrain_link:
        try:
            os.remove(filepath)
            log(f"cleanup_complete | deleted {filename} from disk")
        except Exception:
            pass

# =============================================================================
# RECORDING EXECUTION
# =============================================================================

STOP_REQUESTED = False
CURRENT_PROC = None

def terminate_proc(proc):
    if not proc or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()

def sigterm_handler(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    log("signal_received | saving and wrapping up stream")
    terminate_proc(CURRENT_PROC)

signal.signal(signal.SIGTERM, sigterm_handler)
signal.signal(signal.SIGINT, sigterm_handler)

def record_stream(target_id, session_end):
    global CURRENT_PROC
    target_url = f"https://www.youtube.com/watch?v={target_id}" if len(target_id) == 11 else target_id
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = os.path.join(OUT_DIR, f"{CHANNEL_SLUG}_{timestamp}.ts")
    part_file = out_file + ".part"

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--newline",
        "--no-warnings",
        "--retries", "infinite",
        "--fragment-retries", "infinite",
        "--file-access-retries", "20",
        "--extractor-args", "youtube:player_client=android,web",
        "--hls-use-mpegts",
        "-f", "best[height<=720]/bestvideo[height<=720]+bestaudio/best",
        "-o", out_file,
    ]

    if HAS_COOKIES:
        cmd += ["--cookies", COOKIE_FILE]

    cmd.append(target_url)

    chunk_idx = 1
    log(f"[{format_hms(session_end - time.time())} left] download_started | id={target_id} | chunk={chunk_idx:04d} | client=android")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    CURRENT_PROC = proc

    last_heartbeat = 0
    last_size = -1
    last_growth = time.time()

    while proc.poll() is None and time.time() < session_end and not STOP_REQUESTED:
        time.sleep(HEARTBEAT_SECONDS)
        now = time.time()
        active_path = out_file if os.path.exists(out_file) else part_file
        cur_size = os.path.getsize(active_path) if os.path.exists(active_path) else 0

        if cur_size > last_size:
            last_size = cur_size
            last_growth = now

        if now - last_heartbeat >= HEARTBEAT_SECONDS:
            log(f"[{format_hms(session_end - now)} left] heartbeat | id={target_id} | chunk={chunk_idx:04d} | {cur_size / (1024 * 1024):.1f} MB")
            last_heartbeat = now

        if now - last_growth >= STALL_TIMEOUT_SECONDS:
            log("stream_stalled | attempting download restart")
            terminate_proc(proc)
            break

    if proc.poll() is None:
        terminate_proc(proc)
    CURRENT_PROC = None

    if os.path.exists(part_file) and not os.path.exists(out_file):
        try:
            os.replace(part_file, out_file)
        except Exception:
            pass

    if os.path.exists(out_file) and os.path.getsize(out_file) >= MIN_VALID_SIZE_BYTES:
        size_mb = os.path.getsize(out_file) / (1024 * 1024)
        log(f"download_saved | {size_mb:.1f} MB | {os.path.basename(out_file)}")
        upload_and_cleanup(out_file)
        return True

    if os.path.exists(out_file):
        try:
            os.remove(out_file)
        except Exception:
            pass
    return False

# =============================================================================
# MAIN LOOP
# =============================================================================

session_end_time = time.time() + (HOURS * 3600)

try:
    while time.time() < session_end_time and not STOP_REQUESTED:
        live_id, source = detect_live()
        if live_id:
            log(f"opened_session | live id={live_id} | source={source}")
            record_stream(live_id, session_end_time)
            time.sleep(15)
        else:
            time.sleep(CHECK_INTERVAL_SECONDS)
finally:
    terminate_proc(CURRENT_PROC)
    for item in os.listdir(OUT_DIR):
        if item.endswith(".ts"):
            full_p = os.path.join(OUT_DIR, item)
            if os.path.getsize(full_p) >= MIN_VALID_SIZE_BYTES:
                upload_and_cleanup(full_p)
    log("session_closed | runner exit")
