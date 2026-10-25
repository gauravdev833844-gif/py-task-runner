import contextlib,io,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import update_private_secrets as helper

class PrivateSetupTests(unittest.TestCase):
 def test_dry_run_prints_no_values_and_writes_no_secrets(self):
  with tempfile.TemporaryDirectory() as d:
   config=Path(d)/'rclone.conf';config.write_text('[drive]\ntype = drive\nclient_id = CLIENT_FIXTURE\nclient_secret = SECRET_FIXTURE\ntoken = '+json.dumps({'refresh_token':'REFRESH_FIXTURE'})+'\n')
   result=subprocess.CompletedProcess([],0,'gauravdev833844-gif\n','')
   output=io.StringIO()
   with patch.object(sys,'argv',['helper','--owner','gauravdev833844-gif','--drive-config',str(config),'--dry-run']),patch('shutil.which',return_value='gh'),patch('subprocess.run',return_value=result) as run,contextlib.redirect_stdout(output):helper.main()
   self.assertEqual(run.call_count,1)
   for value in ('CLIENT_FIXTURE','SECRET_FIXTURE','REFRESH_FIXTURE'):self.assertNotIn(value,output.getvalue())
 def test_wrong_owner_stops_before_secret_updates(self):
  with tempfile.TemporaryDirectory() as d:
   config=Path(d)/'rclone.conf';config.write_text('[drive]\ntype = drive\nclient_id = fixture\nclient_secret = fixture\ntoken = {"refresh_token":"fixture"}\n')
   result=subprocess.CompletedProcess([],0,'another-owner\n','')
   with patch.object(sys,'argv',['helper','--owner','gauravdev833844-gif','--drive-config',str(config)]),patch('shutil.which',return_value='gh'),patch('subprocess.run',return_value=result) as run,self.assertRaises(SystemExit):helper.main()
   self.assertEqual(run.call_count,1)

if __name__=='__main__':unittest.main()
