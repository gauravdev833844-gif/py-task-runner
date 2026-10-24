"""A real draft Release upload/readback test using generated media; cleans itself up."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

from publish_recordings import Publisher, PublishError

out = Path('release-backup-validation'); out.mkdir(exist_ok=True)
repo = os.environ['GITHUB_REPOSITORY']
tag = 'recorder-backup-' + os.environ['GITHUB_RUN_ID']
report = {'status': 'FAIL', 'scope': 'One small generated file; Gofile failure simulated, actual draft Release upload and download',
          'release_draft': True, 'telegram_invoked': False, 'cleanup_success': False}
created = False
try:
    p = subprocess.run(['gh', 'release', 'create', tag, '--repo', repo, '--draft',
                        '--target', os.environ['GITHUB_SHA'], '--title', 'Temporary recorder fallback validation',
                        '--notes', 'Generated test media only; draft deleted after readback validation.'],
                       capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError('draft_release_creation_failed')
    created = True
    with tempfile.TemporaryDirectory() as d:
        root = Path(d); media = root/'media'; media.mkdir()
        source = media/'generated.ts'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=25',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '2',
                        '-c:v', 'mpeg2video', '-c:a', 'mp2', str(source)], check=True, capture_output=True)
        original = hashlib.sha256(source.read_bytes()).hexdigest()
        pub = Publisher(media, out/'upload-report.json', budget=180, release_fallback=True)
        with patch.object(pub, 'gofile', side_effect=PublishError('simulated_gofile_unavailable')):
            result = pub.run()
        if result:
            raise RuntimeError('release_fallback_not_confirmed')
        data = json.loads((out/'upload-report.json').read_text())
        if data['files'][0]['receipts'][0]['provider'] != 'github_release':
            raise RuntimeError('wrong_fallback_provider')
        download = root/'download'; download.mkdir()
        p = subprocess.run(['gh', 'release', 'download', tag, '--repo', repo, '--dir', str(download),
                            '--pattern', original[:20] + '-part-00000.ts'], capture_output=True, timeout=60)
        if p.returncode:
            raise RuntimeError('release_readback_failed')
        returned = next(download.glob('*.ts'))
        if hashlib.sha256(returned.read_bytes()).hexdigest() != original:
            raise RuntimeError('release_readback_checksum_mismatch')
        subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(returned), '-f', 'null', '-'],
                       capture_output=True, check=True, timeout=30)
        report.update(status='PASS', bytes=source.stat().st_size, readback_sha256_matches=True,
                      full_audio_video_decode=True, source_preserved=source.exists())
except Exception as error:
    report['failure'] = str(error) if isinstance(error, RuntimeError) else type(error).__name__
finally:
    if created:
        cleanup = subprocess.run(['gh', 'release', 'delete', tag, '--repo', repo, '--yes', '--cleanup-tag'],
                                 capture_output=True, timeout=30)
        report['cleanup_success'] = cleanup.returncode == 0
    if not report['cleanup_success']:
        report['status'] = 'FAIL'
    (out/'result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))
raise SystemExit(0 if report['status'] == 'PASS' else 1)
