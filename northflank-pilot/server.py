"""Read-only health endpoint and ONE bounded recording diagnostic; not an overnight recorder."""
import http.server
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading

state={'service':'youtube-cloud-pilot','state':'starting','capture_passed':False}
lock=threading.Lock()


def update(**fields):
    with lock: state.update(fields)


def run_probe():
    value=os.environ.pop('YT_COOKIES','')
    if not value:
        update(state='missing_cookie_binding')
        print('PILOT_MISSING_YT_COOKIES: add a private runtime secret and redeploy',flush=True)
        return
    try:
        with tempfile.TemporaryDirectory(prefix='youtube-pilot-private-') as private:
            cookie=pathlib.Path(private)/'cookies.txt'
            cookie.write_text(value);cookie.chmod(0o600);value=''
            output=pathlib.Path(private)/'result'
            update(state='testing')
            process=subprocess.run([sys.executable,'/app/probe_live.py','--channel',os.environ.get('CHANNEL_HANDLE','@SkyNews'),
                                    '--client','web_safari','--cookies',str(cookie),'--out',str(output)],
                                   capture_output=True,text=True,timeout=180)
            report_path=output/'result.json'
            if report_path.exists():
                report=json.loads(report_path.read_text())
                # probe_live.py emits only sanitized metadata, never cookie values or media URLs.
                print('PILOT_RESULT '+json.dumps(report),flush=True)
                update(state='complete' if report.get('status')=='PASS' else 'capture_failed',
                       capture_passed=report.get('status')=='PASS',result=report.get('status'))
            else:
                update(state='test_failed',result='no_result_file')
                print('PILOT_FAILED: no sanitized result file; raw child output withheld',flush=True)
    except subprocess.TimeoutExpired:
        update(state='test_failed',result='process_timeout')
        print('PILOT_FAILED: process timeout',flush=True)
    except Exception as error:
        update(state='test_failed',result=type(error).__name__)
        print('PILOT_FAILED '+type(error).__name__,flush=True)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/','/healthz'):
            self.send_error(404);return
        with lock: response=json.dumps(state).encode()
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.send_header('Cache-Control','no-store')
        self.send_header('Content-Length',str(len(response)))
        self.end_headers();self.wfile.write(response)
    def log_message(self,*args):
        pass


if __name__=='__main__':
    threading.Thread(target=run_probe,daemon=True).start()
    server=http.server.ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8080'))),Handler)
    print('PILOT_HEALTH_READY: one test only; no uploads and no overnight recording',flush=True)
    server.serve_forever()
