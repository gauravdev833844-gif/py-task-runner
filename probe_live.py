"""Bounded YouTube capture check. Never exports cookie contents or signed media URLs."""
import argparse
import datetime
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error

FORMAT = 'b[height=720][protocol*=m3u8]/b[protocol*=m3u8]/b[height=720]/b'


def reason(text):
    text = text.casefold()
    if 'tunnel connection failed: 403' in text or 'connect tunnel failed' in text:
        return 'proxy_access_denied'
    if "confirm you’re not a bot" in text or "confirm you're not a bot" in text:
        return 'youtube_bot_verification'
    if 'not currently live' in text or 'live event will begin' in text:
        return 'channel_not_live'
    if 'requested format is not available' in text or 'no video formats' in text:
        return 'no_matching_media_format'
    if 'http error 403' in text:
        return 'youtube_media_403'
    if 'http error 429' in text:
        return 'youtube_rate_limit'
    if 'private video' in text or 'sign in' in text:
        return 'youtube_authentication_required'
    return 'extraction_or_download_failed'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--channel', default='@SkyNews')
    parser.add_argument('--client', choices=['web_safari', 'ios', 'android', 'default'], default='web_safari')
    parser.add_argument('--cookies', default='')
    parser.add_argument('--out', default='probe-results')
    args = parser.parse_args()
    # Restrict destinations; never send a cookie file to an arbitrary input URL.
    if re.fullmatch(r'@[A-Za-z0-9_.-]+', args.channel):
        url = 'https://www.youtube.com/' + args.channel + '/live'
    elif re.fullmatch(r'UC[A-Za-z0-9_-]{22}', args.channel):
        url = 'https://www.youtube.com/channel/' + args.channel + '/live'
    else:
        parser.error('channel must be a YouTube @handle or UC channel ID')
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    report = {'tested_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'channel': args.channel, 'client': args.client, 'cookies_used': bool(args.cookies),
              'status': 'UNVERIFIED', 'captured_seconds': 0}
    version = subprocess.run([sys.executable, '-m', 'yt_dlp', '--version'], capture_output=True, text=True)
    report['yt_dlp_version'] = version.stdout.strip()
    try:
        with tempfile.TemporaryDirectory(prefix='yt-probe-private-') as private:
            base = [sys.executable, '-m', 'yt_dlp', '--no-config', '--no-warnings', '--js-runtimes', 'node',
                    '--socket-timeout', '10', '--retries', '0', '--extractor-retries', '0', '--no-playlist', '-f', FORMAT]
            if args.client != 'default':
                base += ['--extractor-args', 'youtube:player_client=' + args.client]
            try:
                with urllib.request.urlopen(url, timeout=10) as response:
                    response.read(1)
            except urllib.error.URLError as exc:
                if 'tunnel connection failed' in str(exc).casefold():
                    report['status'] = 'proxy_access_denied'
                    return 1
                # HTTP failures may depend on authentication; let yt-dlp diagnose them.
            if args.cookies:
                # Validate without logging parser exceptions, which can contain cookie lines.
                try:
                    jar = http.cookiejar.MozillaCookieJar(args.cookies)
                    jar.load(ignore_discard=True, ignore_expires=True)
                    if not any(c.domain.lstrip('.').endswith('youtube.com') for c in jar):
                        raise ValueError()
                except Exception:
                    report['status'] = 'INVALID_COOKIE_FILE'
                    return 1
                local_cookie = Path(private) / 'cookies.txt'
                shutil.copyfile(args.cookies, local_cookie)
                local_cookie.chmod(0o600)
                base += ['--cookies', str(local_cookie)]
            try:
                probe = subprocess.run(base + ['--skip-download', '--dump-single-json', url],
                                       text=True, capture_output=True, timeout=40)
            except subprocess.TimeoutExpired:
                report['status'] = 'PROBE_TIMEOUT'
                return 1
            if probe.returncode:
                report['status'] = reason(probe.stderr)
                return 1
            try:
                info = json.loads(probe.stdout)
            except ValueError:
                report['status'] = 'INVALID_EXTRACTOR_RESULT'
                return 1
            if not (info.get('is_live') or info.get('live_status') == 'is_live'):
                report['status'] = 'CHANNEL_NOT_LIVE'
                return 1
            video_id = info.get('id', '')
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video_id):
                report['status'] = 'INVALID_VIDEO_ID'
                return 1
            report['video_id'] = video_id
            target = output / 'capture.ts'
            command = base + ['--no-part', '--hls-use-mpegts', '--downloader', 'ffmpeg',
                              '--downloader-args', 'ffmpeg_o:-t 20', '-o', str(target),
                              'https://www.youtube.com/watch?v=' + video_id]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                       start_new_session=True)
            timed_out = False
            try:
                _, errors = process.communicate(timeout=70)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGINT)
                try:
                    _, errors = process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    _, errors = process.communicate()
            report['downloader_exit_code'] = process.returncode
            if timed_out:
                report['status'] = 'CAPTURE_TIMEOUT'
                return 1
            if process.returncode != 0 or not target.is_file():
                report['status'] = reason(errors)
                return 1
            inspect = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                                      '-of', 'json', str(target)], capture_output=True, text=True, timeout=15)
            if inspect.returncode:
                report['status'] = 'UNREADABLE_CAPTURE'
                return 1
            media = json.loads(inspect.stdout)
            seconds = float(media.get('format', {}).get('duration', 0))
            report['captured_seconds'] = round(seconds, 2)
            has_video = any(s.get('codec_type') == 'video' for s in media.get('streams', []))
            if not has_video or seconds < 10:
                report['status'] = 'INSUFFICIENT_VIDEO_CAPTURE'
                return 1
            decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(target),
                                     '-f', 'null', '-'], capture_output=True, timeout=20)
            if decode.returncode:
                report['status'] = 'VIDEO_DECODE_FAILED'
                return 1
            report['status'] = 'PASS'
            return 0
    finally:
        # Only sanitized metadata and captured media are written to public artifacts.
        (output / 'result.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))


if __name__ == '__main__':
    raise SystemExit(main())
