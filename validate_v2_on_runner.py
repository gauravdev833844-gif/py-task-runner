"""One short live engine check. Raw child output and cookies are never published."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

artifact = Path('v2-validation-artifact')
artifact.mkdir(exist_ok=True)
report = {'scope': 'One bounded SkyNews live engine test with existing GitHub YT_COOKIES, not uploaded-cookie validation or an overnight test',
          'status': 'FAIL', 'full_video_audio_decode': False}
try:
    value = os.environ.pop('YT_COOKIES', '')
    if not value:
        raise RuntimeError('missing_cookie_binding')
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        cookie = root/'cookies.txt'; cookie.write_text(value); cookie.chmod(0o600); value = ''
        env = dict(os.environ, CHANNEL_HANDLE='@SkyNews', TARGET_CHANNEL_ID='UCoMdktPbSTixAyNGwb-UYkQ',
                   HOURS='0.0125', USE_COOKIES='true', COOKIE_FILE=str(cookie), OUT_DIR=str(root/'streams'))
        process = subprocess.Popen([sys.executable, 'recorder.py'], env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True)
        try:
            output, _ = process.communicate(timeout=100)
        except subprocess.TimeoutExpired:
            process.send_signal(signal.SIGINT)
            try:
                output, _ = process.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill(); output, _ = process.communicate()
            raise RuntimeError('engine_time_budget_exceeded') from None
        report['recorder_exit_code'] = process.returncode
        paths = list((root/'streams').rglob('*.ts'))
        if process.returncode or not paths:
            lowered = output.lower()
            category = 'authentication_or_botcheck' if any(x in lowered for x in ['not a bot', 'sign in to confirm', 'botcheck']) else 'no_confirmed_capture'
            raise RuntimeError(category)
        capture = max(paths, key=lambda p: p.stat().st_size)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type',
                                '-of', 'json', str(capture)], text=True, capture_output=True, check=True)
        meta = json.loads(probe.stdout)
        duration = float(meta['format']['duration'])
        if duration < 10 or not {'video', 'audio'}.issubset({s['codec_type'] for s in meta['streams']}):
            raise RuntimeError('insufficient_playable_av')
        decode = subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(capture), '-f', 'null', '-'],
                                capture_output=True, timeout=45)
        if decode.returncode:
            raise RuntimeError('whole_file_decode_failed')
        report.update(status='PASS', duration_seconds=duration, bytes=capture.stat().st_size,
                      full_video_audio_decode=True)
        shutil.copyfile(capture, artifact/'capture.ts')
except Exception as error:
    report['failure'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
finally:
    (artifact/'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
raise SystemExit(0 if report['status'] == 'PASS' else 1)
