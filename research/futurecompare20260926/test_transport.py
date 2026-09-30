import json
import unittest
from transport import ReplayNative,OriginalNative,encode,request_line
from audit import BINARIES
from replay_v2 import config,synthetic

class TransportTest(unittest.TestCase):
    def test_full_requests_and_native_outputs_unchanged(self):
        now,responses=synthetic();encoded=encode(responses)
        for label,pair in BINARIES.items():
            original=OriginalNative(pair[0]);cached=ReplayNative(pair[0]);cached.set_responses(responses,encoded)
            try:
                for fee in ('.003','.004','.006'):
                    for aware in (False,True):
                        request=dict(ID='escaping"\\\n',NowNS=now,Config=config(aware,fee),Before=None,Responses=responses)
                        self.assertEqual(json.loads(request_line(request,responses,encoded)),request)
                        a=original.apply(request);b=cached.apply(request)
                        a['Paths'].sort();b['Paths'].sort();self.assertEqual(a,b)
            finally:original.close();cached.close()

if __name__=='__main__':unittest.main()
