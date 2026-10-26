import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import capture_session as capture
import publish_recordings as publish
from rolling_backup import SafetyArchive, probe
import run_upload


class DrivePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='drive-pipeline-test-')
        self.root = Path(self.temp.name)
        self.config = self.root/'rclone.conf'
        self.config.write_text('[drive]\ntype = drive\n')
        self.source = self.root/'video.ts'
        self.source.write_bytes(b'recorded-media-fixture')
        self.metadata = publish.fingerprints(self.source)
        self.good = {'Size': self.metadata['bytes'], 'Hashes': {'MD5': self.metadata['md5']}, 'ID': 'safe_file_id'}
        self.publisher = publish.Publisher(self.root, self.root/'receipt.json', budget=90)
        self.publisher.drive_config = str(self.config)

    def tearDown(self):
        self.temp.cleanup()

    def result(self, code=0, data=None, error=''):
        return SimpleNamespace(returncode=code, stdout=json.dumps(data) if data is not None else '', stderr=error)

    def test_existing_matching_object_skips_copy(self):
        with patch('publish_recordings.shutil.which', return_value='/usr/bin/rclone'), patch('publish_recordings.subprocess.run', return_value=self.result(data=self.good)) as run:
            receipt = self.publisher.google_drive(self.source, self.metadata)
        self.assertTrue(receipt['reconciled_existing'])
        self.assertEqual(run.call_count, 1)
        self.assertTrue(self.source.exists())
        self.assertIn('inherited_acl_not_verified', receipt['sharing'])

    def test_lost_ack_reconciles_without_second_copy(self):
        outcomes = [self.result(4, error='object not found'), self.result(1, error='connection closed after send'), self.result(data=self.good)]
        with patch('publish_recordings.shutil.which', return_value='/usr/bin/rclone'), patch('publish_recordings.subprocess.run', side_effect=outcomes) as run:
            receipt = self.publisher.google_drive(self.source, self.metadata)
        self.assertTrue(receipt['reconciled_after_ambiguous_ack'])
        self.assertEqual(sum('copyto' in call.args[0] for call in run.call_args_list), 1)
        self.assertTrue(self.source.exists())

    def test_copy_timeout_reconciles(self):
        outcomes = [self.result(4, error='object not found'), subprocess.TimeoutExpired('rclone', 1), self.result(data=self.good)]
        with patch('publish_recordings.shutil.which', return_value='/usr/bin/rclone'), patch('publish_recordings.subprocess.run', side_effect=outcomes):
            receipt = self.publisher.google_drive(self.source, self.metadata)
        self.assertTrue(receipt['reconciled_after_ambiguous_ack'])

    def test_precheck_access_denial_never_attempts_upload(self):
        with patch('publish_recordings.shutil.which', return_value='/usr/bin/rclone'), patch('publish_recordings.subprocess.run', return_value=self.result(1, error='HTTP403 forbidden')) as run:
            with self.assertRaises(publish.PublishError):
                self.publisher.google_drive(self.source, self.metadata)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn('copyto', run.call_args.args[0])

    def test_existing_mismatch_is_not_overwritten(self):
        with patch('publish_recordings.shutil.which', return_value='/usr/bin/rclone'), patch('publish_recordings.subprocess.run', return_value=self.result(data={'Size': 0, 'Hashes': {}})) as run:
            with self.assertRaisesRegex(publish.PublishError, 'existing_object_mismatch'):
                self.publisher.google_drive(self.source, self.metadata)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(self.source.read_bytes(), b'recorded-media-fixture')

    def test_failed_drive_has_no_public_fallback(self):
        with patch('publish_recordings.media_ok', return_value=True), patch.object(self.publisher, 'google_drive', side_effect=publish.PublishError('drive_unavailable')), patch.object(self.publisher, 'gofile') as gofile, patch.object(self.publisher, 'release') as release, patch.object(self.publisher, 'resolve_session_url'):
            code = self.publisher.run()
        self.assertEqual(code, 1)
        gofile.assert_not_called()
        release.assert_not_called()
        self.assertTrue(self.source.exists())
        self.assertFalse(json.loads((self.root/'receipt.json').read_text())['all_uploaded'])

    def test_no_media_is_not_upload_success(self):
        self.source.unlink()
        with patch.object(self.publisher, 'resolve_session_url'):
            code = self.publisher.run()
        report = json.loads((self.root/'receipt.json').read_text())
        self.assertEqual(code, 1)
        self.assertEqual(report['media_status'], 'no_media')
        self.assertFalse(report['all_uploaded'])

    def test_guard_halts_for_local_buffer_and_keeps_original(self):
        archive = SimpleNamespace(capture_pressure_reason=None)
        with patch('capture_session.shutil.disk_usage', return_value=SimpleNamespace(free=10**10)):
            reason = capture.pressure_reason(self.root, archive, local_limit=1, reserve=1)
        self.assertEqual(reason, 'capture_local_buffer_limit_reached')
        self.assertTrue(self.source.exists())

    def test_guard_halts_for_low_disk_and_backlog(self):
        archive = SimpleNamespace(capture_pressure_reason=None)
        with patch('capture_session.shutil.disk_usage', return_value=SimpleNamespace(free=1)):
            self.assertEqual(capture.pressure_reason(self.root, archive, reserve=2), 'capture_free_disk_reserve_reached')
        archive.capture_pressure_reason = 'safety_backlog_limit_reached'
        self.assertEqual(capture.pressure_reason(self.root, archive), 'safety_backlog_limit_reached')
        child = unittest.mock.Mock()
        child.poll.return_value = None
        capture.stop_child(child)
        child.send_signal.assert_called_once()

    def test_upload_config_private_and_removed_after_child(self):
        observed = {}
        def child(cmd, env):
            path = Path(env['RCLONE_CONFIG'])
            observed['path'] = path
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('YT_COOKIES', env)
            self.assertNotIn('GH_TOKEN', env)
            self.assertNotIn('RCLONE_CONFIG_TEXT', env)
            return SimpleNamespace(returncode=0)
        with patch.dict(os.environ, {'RCLONE_CONFIG_TEXT': '[drive]\ntype=drive\ntoken={"refresh_token":"dummy"}', 'YT_COOKIES': 'dummy', 'GH_TOKEN': 'dummy'}), patch('run_upload.subprocess.run', side_effect=child), patch('sys.argv',['run_upload.py']):
            self.assertEqual(run_upload.main(), 0)
        self.assertFalse(observed['path'].exists())

    def offline_summary(self, **changes):
        item={'status':'offline','observation_status':'offline','probe_observations':{'live':0,'offline':3,'unknown':0},'failure_reason':None,'saved_file_count':0,'media_saved':False}
        item.update(changes)
        path=self.root/'channel_summary.json'
        path.write_text(json.dumps(item))
        return path

    def test_confirmed_offline_requires_all_strict_evidence(self):
        self.source.unlink()
        self.offline_summary()
        self.assertTrue(run_upload.confirmed_offline(self.root))
        for changes in [{'observation_status':'unknown'}, {'probe_observations':{'live':0,'offline':0,'unknown':0}}, {'probe_observations':{'live':0,'offline':3,'unknown':1}}, {'failure_reason':'botcheck'}, {'auth_blocked':True}, {'saved_file_count':False}]:
            self.offline_summary(**changes)
            self.assertFalse(run_upload.confirmed_offline(self.root),changes)

    def test_offline_missing_or_malformed_or_mixed_summaries_rejected(self):
        self.source.unlink()
        self.assertFalse(run_upload.confirmed_offline(self.root))
        path=self.offline_summary()
        path.write_text('{')
        self.assertFalse(run_upload.confirmed_offline(self.root))
        self.offline_summary()
        (self.root/'other_summary.json').write_text(json.dumps({'observation_status':'unknown'}))
        self.assertFalse(run_upload.confirmed_offline(self.root))

    def test_offline_exemption_never_hides_partial_media_or_guard_halt(self):
        self.offline_summary()
        self.assertFalse(run_upload.confirmed_offline(self.root))
        self.source.unlink()
        (self.root/'capture-guard.json').write_text(json.dumps({'halted':True}))
        self.assertFalse(run_upload.confirmed_offline(self.root))

    def test_explicit_offline_flag_writes_not_applicable_not_uploaded(self):
        self.source.unlink()
        self.offline_summary()
        report=self.root/'publication.json'
        with patch('sys.argv',['run_upload.py','--allow-confirmed-offline','--root',str(self.root),'--report',str(report)]),patch('run_upload.subprocess.run')as child:
            self.assertEqual(run_upload.main(),0)
        child.assert_not_called()
        value=json.loads(report.read_text())
        self.assertEqual(value['publication_status'],'not_applicable')
        self.assertEqual(value['files'],[])
        self.assertFalse(value['all_uploaded'])

    def test_default_does_not_exempt_confirmed_offline(self):
        self.source.unlink()
        self.offline_summary()
        with patch.dict(os.environ,{'RCLONE_CONFIG_TEXT':''}),patch('sys.argv',['run_upload.py','--root',str(self.root)]),patch('run_upload.subprocess.run',return_value=SimpleNamespace(returncode=1))as child:
            self.assertEqual(run_upload.main(),1)
        child.assert_called_once()

    def test_config_normalization_validates_without_guessing_credentials(self):
        raw='[drive]\ntype = drive\nclient_id = own-client\nclient_secret = unchanged-secret\ntoken = {"refresh_token":"dummy","access_token":"dummy-access"}\n'
        for encoded in [raw,'\ufeff'+raw,json.dumps(raw),raw.replace('\n','\\n')]:
            normalized=publish.normalize_rclone_config(encoded)
            self.assertIn('client_secret = unchanged-secret',normalized)
            self.assertEqual(publish.normalize_rclone_config(normalized),normalized)
        for invalid in ['', 'junk', '[drive]\ntype=drive', '[drive]\ntype=drive\ntoken={"access_token":"only"}', '[other]\ntype=drive\ntoken={"refresh_token":"x"}']:
            with self.assertRaises(publish.PublishError):publish.normalize_rclone_config(invalid)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg unavailable')
    def test_real_ffmpeg_finalized_safety_clip_preserves_original(self):
        self.source.unlink()
        chunks = self.root/'_chunks'
        chunks.mkdir()
        source = chunks/'source.ts'
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=10', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=8000', '-t', '3', '-c:v', 'mpeg2video', '-c:a', 'mp2', '-f', 'mpegts', str(source)], check=True, capture_output=True, timeout=20)
        archive = SafetyArchive(self.root, uploader=lambda *args: {}, seconds=5, overlap=1)
        archive.stage(final=True)
        clips = list(archive.work.glob('*.ts'))
        self.assertTrue(clips)
        self.assertTrue(source.exists())
        self.assertGreater(probe(clips[0]), 1)
        self.assertFalse(list(archive.work.glob('*.partial.ts')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
