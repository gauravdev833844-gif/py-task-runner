"""One six-minute recording/upload check; no chaining, Release assets or Telegram."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

from publish_recordings import Publisher

artifact = Path('six-minute-validation')
artifact.mkdir(exist_ok=True)
report = {'status': 'FAIL', 'channel': '@SkyNews', 'monitor_hours': .1,
          'scope': 'One channel, existing GitHub cookie binding; not uploaded-cookie, multi-GB or overnight validation',
          'gofile_per_attempt_cap_seconds': 600, 'validation_upload_budget_seconds': 180,
          'telegram_invoked': False, 'release_backup_enabled': False}
phase = 'setup'
started = time.monotonic()
try:
    value = os.environ.pop('YT_COOKIES', '')
    if not value:
        raise RuntimeError('missing_cookie_binding')
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cookie = root/'cookies.txt'; cookie.write_text(value); cookie.chmod(0o600); value = ''
        env = dict(os.environ, CHANNEL_HANDLE='@SkyNews', TARGET_CHANNEL_ID='UCoMdktPbSTixAyNGwb-UYkQ',
                   HOURS='0.1', USE_COOKIES='true', COOKIE_FILE=str(cookie), OUT_DIR=str(root/'streams'))
        phase = 'capture'
        process = subprocess.Popen([sys.executable, 'recorder.py'], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            output, _ = process.communicate(timeout=450)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT)
            try:
                output, _ = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill(); output, _ = process.communicate()
            raise RuntimeError('capture_time_budget_exceeded') from None
        report['recorder_exit_code'] = process.returncode
        paths = list((root/'streams').rglob('*.ts'))
        if process.returncode or not paths:
            lower = output.lower()
            category = 'authentication_or_botcheck' if any(x in lower for x in ['not a bot', 'sign in to confirm', 'botcheck']) else 'no_confirmed_capture'
            raise RuntimeError(category)
        capture = max(paths, key=lambda p: p.stat().st_size)
        phase = 'decode'
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                'format=duration:stream=codec_type,width,height', '-of', 'json', str(capture)],
                               text=True, capture_output=True, check=True)
        meta = json.loads(probe.stdout)
        duration = float(meta['format']['duration'])
        if duration < 300 or not {'video', 'audio'}.issubset({s['codec_type'] for s in meta['streams']}):
            raise RuntimeError('insufficient_recorded_av_duration')
        decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(capture), '-f', 'null', '-'],
                                capture_output=True, timeout=90)
        if decode.returncode:
            raise RuntimeError('whole_file_decode_failed')
        video = next(s for s in meta['streams'] if s['codec_type'] == 'video')
        report.update(duration_seconds=duration, bytes=capture.stat().st_size, full_video_audio_decode=True,
                      width=video.get('width'), height=video.get('height'))
        phase = 'upload'
        upload_start = time.monotonic()
        result = Publisher(root/'streams', artifact/'upload-report.json', budget=180,
                           release_fallback=False).run()
        report['upload_seconds'] = round(time.monotonic()-upload_start, 2)
        upload = json.loads((artifact/'upload-report.json').read_text())
        report['all_uploaded'] = upload['all_uploaded']
        if result or not upload['all_uploaded']:
            raise RuntimeError('gofile_upload_not_confirmed')
        report['status'] = 'PASS'
except Exception as error:
    report['failed_phase'] = phase
    report['failure'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
finally:
    report['elapsed_seconds'] = round(time.monotonic()-started, 2)
    (artifact/'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
raise SystemExit(0 if report['status'] == 'PASS' else 1)
