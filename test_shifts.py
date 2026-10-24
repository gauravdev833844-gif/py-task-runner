import json
import os
import unittest
from unittest.mock import patch
from shift_plan import plan, STEP, WINDOW
from chain_shift import dispatch_body, main as chain_main


class ShiftTests(unittest.TestCase):
    def test_overnight_windows_overlap_and_cover_twelve_hours(self):
        # Relative planning works equally for 19:00, 20:30 and midnight manual starts.
        for start in (0, 19*3600, 20*3600+1800, 24*3600):
            windows=[]
            index=0
            now=start
            while True:
                result=plan(start,12,now,index)
                windows.append((now, now+result['duration_hours']*3600))
                if not result['chain']: break
                now=result['next_at']
                index=result['next_index']
            self.assertEqual([a-start for a,b in windows],[0,10800,21600,32400])
            self.assertEqual(windows[-1][1],start+12*3600)
            for first,second in zip(windows,windows[1:]):
                self.assertEqual(first[1]-second[0],2*3600)

    def test_half_hour_next_runner_delay_preserves_overlap(self):
        start=1000
        first=plan(start,12,start)
        second_start=first['next_at']+1800
        second=plan(start,12,second_start,1)
        self.assertLess(second_start,start+first['duration_hours']*3600)
        self.assertEqual(second['next_at'],start+2*STEP)

    def test_late_runner_skips_obsolete_continuations(self):
        result=plan(0,12,8*3600,1)
        self.assertFalse(result['chain'])
        self.assertEqual(result['duration_hours'],4)

    def test_expired_session_does_not_record_or_continue(self):
        result=plan(0,12,13*3600,4)
        self.assertFalse(result['active'])
        self.assertFalse(result['chain'])

    def test_short_session_needs_no_second_shift(self):
        result=plan(0,2,0)
        self.assertFalse(result['chain'])
        self.assertEqual(result['duration_hours'],2)

    def test_input_bounds(self):
        for hours in (0,-1,25,float('nan')):
            with self.assertRaises(ValueError): plan(0,hours,0)
        with self.assertRaises(ValueError): plan(1000,12,0)

    def test_twenty_four_hour_session_stays_bounded(self):
        for index in range(8):
            result=plan(0,24,index*STEP,index)
            self.assertLessEqual(result['duration_hours']*3600,WINDOW)
            self.assertEqual(result['chain'],index<7)

    def test_dispatch_keeps_same_session_and_branch(self):
        env={'WORKFLOW_REF':'test-branch','TOTAL_HOURS':'12','SESSION_START':'1000',
             'SESSION_ID':'123','NEXT_INDEX':'1'}
        with patch.dict(os.environ,env):
            body=dispatch_body()
        self.assertEqual(body['ref'],'test-branch')
        self.assertEqual(body['inputs']['session_start'],'1000')
        self.assertEqual(body['inputs']['shift_index'],'1')

    def test_actual_dispatch_code_sends_bounded_continuation(self):
        env={'WORKFLOW_REF':'test-branch','TOTAL_HOURS':'12','SESSION_START':'1000',
             'SESSION_ID':'123','NEXT_INDEX':'1','NEXT_AT':'1000','DEADLINE':'50000',
             'GITHUB_REPOSITORY':'owner/repo','GH_TOKEN':'dummy-test-placeholder'}
        class Response:
            status=204
            def __enter__(self): return self
            def __exit__(self,*args): pass
        with patch.dict(os.environ,env), patch('chain_shift.time.time',return_value=1001), \
             patch('chain_shift.urllib.request.urlopen',return_value=Response()) as request:
            chain_main()
        sent=request.call_args.args[0]
        self.assertEqual(sent.full_url,'https://api.github.com/repos/owner/repo/actions/workflows/record.yml/dispatches')
        self.assertEqual(json.loads(sent.data)['inputs']['shift_index'],'1')
        self.assertEqual(request.call_count,1)


if __name__ == '__main__':
    unittest.main()
