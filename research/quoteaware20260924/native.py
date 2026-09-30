"""Public-loopback native paper-cycle transport; no credentials."""
import json
import os
import selectors
import subprocess

class Native:
    def __init__(self,binary):
        self.p=subprocess.Popen([str(binary),'-test.run=^TestObservedCycleDriver$','-test.timeout=0'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1,env={**os.environ,'GOMAXPROCS':'1'})
    def apply(self,request):
        self.p.stdin.write(json.dumps(request,separators=(',',':'),allow_nan=False)+'\n');self.p.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(self.p.stdout,selectors.EVENT_READ)
            if not selector.select(30):self.p.kill();raise RuntimeError('native cycle timeout')
        line=self.p.stdout.readline()
        if not line.startswith('{'):raise RuntimeError('native cycle failed: '+line+self.p.stderr.read())
        result=json.loads(line);assert result['ID']==request['ID'];return result
    def close(self):
        self.p.stdin.close();self.p.stdin=None
        stdout,stderr=self.p.communicate(timeout=10)
        assert self.p.returncode==0,(stdout,stderr)

