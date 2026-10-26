import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

import diagnostic_canary as canary

VIDEO='abcdefghijk'
CHANNEL='UC'+'x'*22
URL='https://www.youtube.com/watch?v='+VIDEO

def metadata():
    return {'id':VIDEO,'channel_id':CHANNEL,'is_live':True,'live_status':'is_live',
            'formats':[{'url':'https://example.invalid/signed-secret','protocol':'m3u8_native',
                        'vcodec':'avc1','acodec':'mp4a','height':720,'tbr':4000}]}

class CanaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='canary-tests-')
        self.root=Path(self.temporary.name)
        self.env=patch.dict(os.environ,{'CANARY_VIDEO_ID':VIDEO,'CANARY_CHANNEL_ID':CHANNEL,
                                      'CANARY_SOURCE_URL':URL,'YT_COOKIES':'private-cookie-marker',
                                      'RCLONE_CONFIG_TEXT':'private-config-marker','CANARY_CLEANUP':'false'})
        self.env.start()
        canary.DEADLINE=None
    def tearDown(self):
        self.env.stop();self.temporary.cleanup();canary.DEADLINE=None
    def report(self):
        return json.loads((self.root/'canary-report.json').read_text())
    def test_explicit_selection(self):
        self.assertTrue(canary.valid_selection(URL,VIDEO,CHANNEL))
        for url in [URL+'&list=evil',URL+'#fragment',URL.replace('www.youtube.com','example.com'),URL.replace('https:','http:')]:
            self.assertFalse(canary.valid_selection(url,VIDEO,CHANNEL))
    def test_identity_and_live_status_required(self):
        for field,value in [('channel_id','UC'+'z'*22),('id','zyxwvutsrqp'),('live_status',None),('is_live',None)]:
            d=metadata();d[field]=value
            with self.assertRaises(canary.Failure):canary.select_format(d,VIDEO,CHANNEL)
    def test_partial_json_is_not_playable(self):
        d=metadata();d['formats']=[]
        with self.assertRaisesRegex(canary.Failure,'NO_PLAYABLE'):canary.select_format(d,VIDEO,CHANNEL)
        d['formats']=[dict(metadata()['formats'][0],acodec='none')]
        with self.assertRaisesRegex(canary.Failure,'NO_PLAYABLE'):canary.select_format(d,VIDEO,CHANNEL)
    def test_cookie_denial_on_exit_zero_fails_without_fallback(self):
        with patch.object(canary,'run',return_value=(0,json.dumps(metadata()).encode(),b'WARNING: The provided cookies are no longer valid.')),patch.object(canary,'drive_folder')as drive:
            code=canary.execute(self.root)
        self.assertEqual(code,2);drive.assert_not_called()
        self.assertEqual(self.report()['reason'],'AUTH_BLOCKED')
        self.assertNotIn('private-cookie-marker',(self.root/'canary-report.json').read_text())
        self.assertNotIn('signed-secret',(self.root/'canary-report.json').read_text())
    def test_timeout_never_passes(self):
        with patch.object(canary,'run',side_effect=canary.Failure('OPERATION_TIMEOUT')):
            self.assertEqual(canary.execute(self.root),2)
        self.assertEqual(self.report()['reason'],'OPERATION_TIMEOUT')
    def test_no_media_never_passes(self):
        def fake_run(command,**kwargs):
            if '-m' in command:return 0,json.dumps(metadata()).encode(),b''
            return 0,b'',b''
        with patch.object(canary,'run',side_effect=fake_run),patch.object(canary,'drive_folder',return_value='folder123'):
            self.assertEqual(canary.execute(self.root),2)
        self.assertFalse(self.report()['capture_test_passed'])
    def run_mock_capture(self,matching=True,hash_key="md5"):
        def fake_run(command,**kwargs):
            if '-m' in command:return 0,json.dumps(metadata()).encode(),b''
            if command[0]=='ffmpeg':Path(command[-1]).write_bytes(b'valid-media-placeholder'*100)
            return 0,b'',b''
        def fake_drive(command,config,timeout=45):
            if command[0]=='copyto':return b''
            if command[0]=='lsjson':
                media=self.root/'captured.ts'
                return json.dumps({'ID':'file12345','Size':media.stat().st_size,'Hashes':{hash_key:canary.md5_file(media)if matching else 'bad'}}).encode()
            return b''
        with patch.object(canary,'run',side_effect=fake_run),patch.object(canary,'drive_folder',return_value='folder123'),patch.object(canary,'drive',side_effect=fake_drive),patch.object(canary,'owner_only')as privacy,patch.object(canary,'inspect_media',return_value={'audio_present':True,'video_present':True}):
            code=canary.execute(self.root)
        return code,privacy
    def test_verified_receipt_required_for_success(self):
        code,privacy=self.run_mock_capture()
        self.assertEqual(code,0);privacy.assert_called_once()
        data=self.report();self.assertTrue(data['capture_test_passed']);self.assertTrue(data['drive_test_passed'])
        self.assertTrue(data['drive_receipt']['md5_match']);self.assertTrue(data['media_preserved_locally'])
        self.assertFalse(data['large_6gb_tested']);self.assertFalse(data['shift_handover_tested'])
    def test_uppercase_remote_hash_key_also_verifies_receipt(self):
        code,privacy=self.run_mock_capture(hash_key='MD5')
        self.assertEqual(code,0)
        self.assertTrue(self.report()['drive_receipt']['md5_match'])
    def test_remote_md5_requires_valid_unambiguous_digest(self):
        good='a1'*16
        for key in ['md5','MD5','Md5']:
            self.assertEqual(canary.remote_md5({'Hashes':{key:good.upper()}}),good)
        for value in [None,0,'bad',[],good+'0']:
            self.assertIsNone(canary.remote_md5({'Hashes':{'md5':value}}))
        self.assertIsNone(canary.remote_md5({'Hashes':{'md5':good,'MD5':'b2'*16}}))
        self.assertIsNone(canary.remote_md5({'Hashes':{'sha1':good}}))
    def test_hash_mismatch_fails_and_preserves_media(self):
        code,privacy=self.run_mock_capture(matching=False)
        self.assertEqual(code,2);privacy.assert_not_called()
        data=self.report();self.assertEqual(data['reason'],'DRIVE_SIZE_OR_HASH_MISMATCH')
        self.assertTrue(data['media_preserved_locally']);self.assertFalse(data['drive_test_passed'])
    def test_environment_does_not_forward_secret_values(self):
        with patch.dict(os.environ,{'GH_TOKEN':'fake','RCLONE_CONFIG_TEXT':'fake','YT_COOKIES':'fake','TELEGRAM_BOT_TOKEN':'fake'}):
            env=canary.child_env()
        for name in ['GH_TOKEN','RCLONE_CONFIG_TEXT','YT_COOKIES','TELEGRAM_BOT_TOKEN']:self.assertNotIn(name,env)
    def test_private_file_mode(self):
        path=self.root/'private'
        canary.private_write(path,'fake')
        self.assertEqual(path.stat().st_mode&0o777,0o600)
    def test_owner_only_rejects_shared_folder(self):
        config=self.root/'rclone.conf';config.write_text('[drive]\ntoken={"access_token":"fake"}\n')
        reply=io.BytesIO(json.dumps({'permissions':[{'role':'owner','type':'user'},{'role':'reader','type':'anyone'}]}).encode())
        with patch.object(canary,'urlopen',return_value=reply):
            with self.assertRaisesRegex(canary.Failure,'OWNER_ONLY'):canary.owner_only(config,'folder123')
    def test_actual_synthetic_media_decode_and_corruption(self):
        path=self.root/'synthetic.ts'
        p=subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=10',
                          '-f','lavfi','-i','sine=frequency=1000:sample_rate=16000','-t','62',
                          '-c:v','mpeg2video','-c:a','mp2','-f','mpegts','-y',str(path)],capture_output=True,timeout=30)
        self.assertEqual(p.returncode,0)
        report=canary.inspect_media(path)
        self.assertTrue(report['sample_decode_passed']);self.assertTrue(report['audio_present'])
        path.write_bytes(b'not-real-video')
        with self.assertRaisesRegex(canary.Failure,'MEDIA_PROBE_FAILED'):canary.inspect_media(path)

if __name__=='__main__':unittest.main(verbosity=2)
