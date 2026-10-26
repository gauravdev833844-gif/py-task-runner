"""Truthful source errors and bounded transport retry, without outside requests."""
import argparse,contextlib,io,json,subprocess,unittest
from unittest.mock import Mock,patch
import requests
import hls_capture as h

class HLSTransportTests(unittest.TestCase):
    def args(self):
        return argparse.Namespace(metadata=None,url='https://example.invalid/watch',output='/tmp/not-created.ts',format='best',client='default',cookies=None)
    def test_invalid_cookie_warning_even_exit_zero_stops_before_capture(self):
        args=self.args();result=subprocess.CompletedProcess([],0,json.dumps({'is_live':True,'url':'https://example.invalid/signed'}),'WARNING: cookies are no longer valid')
        with patch.object(h.subprocess,'run',return_value=result),contextlib.redirect_stdout(io.StringIO())as output:
            self.assertIsNone(h.extract(args))
        self.assertIn('cookies are no longer valid',output.getvalue())
        self.assertNotIn('signed',output.getvalue())
    def test_unconfirmed_or_ended_metadata_never_starts_transport(self):
        for metadata in ({'url':'https://example.invalid/media'},{'is_live':False,'live_status':'was_live','url':'https://example.invalid/media'}):
            with patch.object(h,'extract',return_value=metadata),patch.object(h,'fallback_capture')as fallback,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(h.capture(self.args()),2)
                fallback.assert_not_called()
    def session(self,request):
        session=Mock();session.http.headers={};session.http.request=request
        return session
    def error(self,status):
        response=requests.Response();response.status_code=status;response.headers['Retry-After']='0.01'
        return requests.HTTPError('test-only',response=response)
    def test_explicit_denial_is_not_retried(self):
        for status in (401,403,429):
            request=Mock(side_effect=self.error(status));session=self.session(request)
            state=h.configure_session(session,{},None)
            with self.assertRaises(requests.HTTPError):session.http.request('GET','https://example.invalid/segment')
            self.assertEqual(request.call_count,1)
            self.assertIn(state['denial'],('access_denied','rate_limited'))
    def test_transient_network_retry_keeps_reader_route(self):
        expected=object();request=Mock(side_effect=[self.error(503),self.error(503),expected]);session=self.session(request)
        state=h.configure_session(session,{},None)
        with patch.object(h.time,'sleep'):
            actual=session.http.request('GET','https://example.invalid/segment')
        self.assertIs(actual,expected);self.assertEqual(state['retries'],2);self.assertEqual(request.call_count,3)
    def test_nightly_selector_requires_combined_720_hls(self):
        from yt_dlp import YoutubeDL
        selector='best[height<=720][protocol*=m3u8][vcodec!=none][acodec!=none]'
        formats=[
            {'format_id':'22','height':720,'protocol':'https','vcodec':'avc1','acodec':'aac','url':'https://example.invalid/progressive','ext':'mp4'},
            {'format_id':'95','height':720,'protocol':'m3u8_native','vcodec':'avc1','acodec':'aac','url':'https://example.invalid/live.m3u8','ext':'mp4'},
            {'format_id':'96','height':1080,'protocol':'m3u8_native','vcodec':'avc1','acodec':'aac','url':'https://example.invalid/1080.m3u8','ext':'mp4'}]
        with YoutubeDL({'quiet':True,'no_warnings':True}) as ydl:
            selected=list(ydl.build_format_selector(selector)({'formats':formats,'has_merged_format':True,'incomplete_formats':False}))
        self.assertEqual([x['format_id'] for x in selected],['95'])
    def test_tls_error_is_never_retried(self):
        request=Mock(side_effect=requests.exceptions.SSLError('test-only'));session=self.session(request)
        h.configure_session(session,{},None)
        with patch.object(h.time,'sleep')as sleep,self.assertRaises(requests.exceptions.SSLError):session.http.request('GET','https://example.invalid/segment')
        self.assertEqual(request.call_count,1);sleep.assert_not_called()

if __name__=='__main__':unittest.main()
