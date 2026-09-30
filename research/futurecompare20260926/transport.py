"""Same frozen native driver; encode shared public responses once per minute."""
import json
import selectors
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'quoteaware20260924'))
from native import Native as OriginalNative

def encode(v):return json.dumps(v,separators=(',',':'),allow_nan=False)

def request_line(request,responses,encoded):
    assert request['Responses'] is responses
    return encode({k:v for k,v in request.items() if k!='Responses'})[:-1]+',"Responses":'+encoded+'}\n'

class ReplayNative(OriginalNative):
    def set_responses(self,responses,encoded):
        self.responses=responses;self.encoded=encoded
    def apply(self,request):
        line=request_line(request,self.responses,self.encoded)
        self.p.stdin.write(line);self.p.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(self.p.stdout,selectors.EVENT_READ)
            if not selector.select(30):self.p.kill();raise RuntimeError('native cycle timeout')
        line=self.p.stdout.readline()
        if not line.startswith('{'):raise RuntimeError('native cycle failed: '+line+self.p.stderr.read())
        result=json.loads(line);assert result['ID']==request['ID'];return result
