import gzip
import hashlib
import io
import json
from pathlib import Path
import tempfile
import signal
import unittest
import urllib.error
from unittest.mock import patch
import recorder
from recorder import NoRedirect,MAX_BODY,endpoints,fetch,publish,slot_action,write_capture


class Response(io.BytesIO):
    def __init__(self,raw,status=200):super().__init__(raw);self.status=status


class Opener:
    def __init__(self,raw,status=200):self.raw=raw;self.status=status
    def open(self,request,timeout):
        assert request.get_method()=='GET' and request.get_header('Authorization') is None
        return Response(self.raw,self.status)


class RecorderTests(unittest.TestCase):
    def test_raw_bytes_and_public_method(self):
        raw=b'{ "message": "raw bytes preserved" }\n'
        r=fetch(Opener(raw),'ranks',endpoints()[0][1],1)
        import base64
        self.assertEqual(base64.b64decode(r['body_b64']),raw)
        self.assertEqual(r['body_sha256'],hashlib.sha256(raw).hexdigest())
        self.assertTrue(r['wall_clock_stable']);self.assertFalse(r['credentials_used'])
    def test_http_error_body_retained(self):
        class ErrorOpener:
            def open(self,request,timeout):raise urllib.error.HTTPError(request.full_url,503,'unavailable',{},Response(b'{"error":"expired"}'))
        r=fetch(ErrorOpener(),'ranks',endpoints()[0][1],1)
        self.assertEqual(r['status'],503);self.assertIsNone(r['error']);self.assertGreater(r['body_bytes'],0)
    def test_rate_limit_is_visible(self):self.assertEqual(fetch(Opener(b'limit',429),'book',endpoints()[3][1],1)['status'],429)
    def test_truncation_is_explicit(self):
        r=fetch(Opener(b'x'*(MAX_BODY+1)),'book',endpoints()[3][1],1)
        self.assertTrue(r['body_truncated']);self.assertEqual(r['body_bytes'],MAX_BODY)
    def test_backward_clock_is_not_silently_accepted(self):
        times=iter([100,90]);mono=iter([1000,1010])
        r=fetch(Opener(b'{}'),'book',endpoints()[3][1],1,lambda:next(times),lambda:next(mono))
        self.assertFalse(r['wall_clock_stable'])
    def test_schedule_boundaries(self):
        self.assertEqual(slot_action(99,100),'wait');self.assertEqual(slot_action(100,100),'capture')
        self.assertEqual(slot_action(45_000_000_099,100),'capture');self.assertEqual(slot_action(45_000_000_100,100),'gap')
    def test_archive_hash_and_incomplete_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);r=fetch(Opener(b'{}'),'ranks',endpoints()[0][1],1)
            receipt=write_capture(root,0,1,[r],'capture_deadline')
            raw=(root/receipt['archive']).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(),receipt['archive_sha256'])
            self.assertEqual(json.loads(gzip.decompress(raw)),r)
            self.assertFalse(receipt['complete']);self.assertEqual(receipt['attempted_requests'],1)
    def test_evidence_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'record';publish(p,b'old')
            with self.assertRaises(RuntimeError):publish(p,b'new')
            self.assertEqual(p.read_bytes(),b'old')
    def test_no_redirect_and_fixed_endpoints(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))
        self.assertEqual(len(endpoints()),11)
        self.assertTrue(all(u.startswith('https://api.poloniex.com/markets') for _,u in endpoints()[1:]))
    def bounded_run(self,free,status):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);start=1790215200000000000+15_000_000_000
            p=dict(format='poloniex-public-receipts-v1',symbols=list(recorder.SYMBOLS),endpoints=[list(x) for x in endpoints()],
                slots=10080,period_ns=recorder.MINUTE,slot_window_ns=45_000_000_000,start_ns=start,end_exclusive_ns=start+10080*recorder.MINUTE,
                max_bytes=2<<30,minimum_free_bytes=20<<30,credentials_used=False,external_orders=False,recorder_sha256=recorder.sha(recorder.__file__))
            (root/'protocol.json').write_bytes(recorder.encode(p))
            r=fetch(Opener(b'limit',status),'ranks',endpoints()[0][1],1)
            previous={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
            try:
                with patch('recorder.time.time_ns',return_value=start+1_000_000_000),patch('recorder.shutil.disk_usage') as disk,patch('recorder.fetch',return_value=r) as requests:
                    disk.return_value.free=free
                    recorder.run(root,recorder.sha(root/'protocol.json'))
                    return json.loads((root/'stopped.json').read_text()),requests.call_count,list(root.glob('minute_*.receipt.json'))
            finally:
                for s,h in previous.items():signal.signal(s,h)
    def test_rate_limit_stops_before_second_request(self):
        result,calls,receipts=self.bounded_run(100<<30,429)
        self.assertEqual(result['reason'],'rate_limited');self.assertEqual(calls,1);self.assertEqual(len(receipts),1)
    def test_low_space_stops_before_network(self):
        result,calls,receipts=self.bounded_run(1<<30,200)
        self.assertEqual(result['reason'],'free_storage_bound');self.assertEqual(calls,0);self.assertFalse(receipts)


if __name__=='__main__':unittest.main()
