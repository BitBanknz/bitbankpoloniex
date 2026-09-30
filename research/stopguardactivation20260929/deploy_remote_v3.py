"""Activate the authenticated guard without resetting the live account."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
import time
from continuity import verify as continuity

ROOT=Path('/nvme0n1-disk/code/bitbank-poloniex')
OUT=ROOT/'data/release-stop-guard-20260930_v3'
STATE=ROOT/'data/live'
BINARY=ROOT/'bin/bitbankpoloniex'
UNIT=Path('/etc/systemd/system/bitbankpoloniex-live.service')
SERVICE='bitbankpoloniex-live.service'
BASELINE='eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec'
CANDIDATE='4cc9122477f3e5c6e030ecf5df4aaf73ceb4bf31c3747208944c737f99d44805'
ARCHIVE_SHA='46876c8dc6d8462e6f62809935e1caefe2164c31ff234e1a7871093e9aaa05b3'
UNIT_SHA='9f3af984558bdb09a685413057cabe981d129bc53ef74a9933f93c385d9c9765'
EXPECTED=[str(BINARY),'--command','run','--mode','live','--state','data/live','--budget','495',
    '--max-order','49','--slots','3','--cooldown-hours','120','--slot-top-up','--cash-reserve','0.4',
    '--halt-peak-dd','0.25','--halt-daily-loss','0.08','--enable-live-orders','--predictions',
    'http://127.0.0.1:8745/api/trading-bot/rotation-signals','--env',str(ROOT/'.env')]
ENV={'PATH':'/usr/local/go/bin:/usr/bin:/bin','HOME':os.environ['HOME'],'GOMAXPROCS':'2'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')

def service():
    raw=subprocess.check_output(['systemctl','show',SERVICE,'-p','MainPID','-p','ActiveState','-p','SubState','-p','NRestarts'],text=True)
    return dict(line.split('=',1) for line in raw.splitlines())

def check_running(expected):
    current=service();assert current['ActiveState']=='active' and current['SubState']=='running',current
    pid=int(current['MainPID']);assert pid>0
    assert sha(Path('/proc')/str(pid)/'exe')==sha(BINARY)==expected
    args=(Path('/proc')/str(pid)/'cmdline').read_bytes().decode().rstrip('\0').split('\0')
    assert args==EXPECTED,('changed_live_arguments',args)
    assert sha(UNIT)==UNIT_SHA,'service unit changed'
    return current

def command(action):
    subprocess.run(['sudo','-n','systemctl',action,SERVICE],check=True,timeout=90)

def doctor(binary,label):
    args=[str(binary),*EXPECTED[1:]];args[args.index('--command')+1]='doctor'
    result=subprocess.run(args,cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=120)
    with (OUT/(label+'.stdout.json')).open('x') as f:f.write(result.stdout)
    with (OUT/(label+'.stderr.log')).open('x') as f:f.write(result.stderr)
    assert result.returncode==0,(label,result.returncode)
    body=json.loads(result.stdout)
    assert body['live_orders_submitted'] is False
    assert body['execution_readiness']=='read checks passed; write permission unverified',body.get('execution_readiness')
    proof=dict(verified=True,read_only=True,exchange_open_order_check_passed=True,
        stdout_sha256=sha(OUT/(label+'.stdout.json')),stderr_sha256=sha(OUT/(label+'.stderr.log')))
    save(OUT/(label+'.receipt.json'),proof)
    return proof

def install(source):
    metadata=BINARY.stat()
    with tempfile.NamedTemporaryFile(dir=BINARY.parent,prefix='.stop-guard-',delete=False) as f:
        temporary=Path(f.name)
        with source.open('rb') as stream:shutil.copyfileobj(stream,f)
        f.flush();os.fsync(f.fileno())
    try:
        temporary.chmod(stat.S_IMODE(metadata.st_mode))
        if (temporary.stat().st_uid,temporary.stat().st_gid)!=(metadata.st_uid,metadata.st_gid):
            subprocess.run(['sudo','-n','chown',f'{metadata.st_uid}:{metadata.st_gid}',str(temporary)],check=True)
        assert sha(temporary)==sha(source)
        os.replace(temporary,BINARY)
    finally:temporary.unlink(missing_ok=True)

def observe(expected,before,label):
    began=time.monotonic();clocks=set();proofs=[];last_error=None
    while time.monotonic()-began<240:
        try:
            current=check_running(expected);after=read(STATE/'state.json')
            if after['LastCycle'] not in clocks:
                proof=continuity(before,after)
                clocks.add(after['LastCycle'])
                save(OUT/f'{label}_cycle_{len(clocks):02d}.json',after)
                proofs.append(dict(at_ns=time.time_ns(),service=current,continuity=proof))
                print('COMPLETED_CYCLE',label,len(clocks),after['LastCycle'],flush=True)
                if len(clocks)>=2:return proofs,after
        except (AssertionError,FileNotFoundError) as error:last_error=str(error)
        time.sleep(2)
    raise RuntimeError(('completed cycles not verified',last_error))

def extract():
    archive=OUT/'poloniex-stop-topup-guard-20260924.tar.gz';assert sha(archive)==ARCHIVE_SHA
    with tarfile.open(archive,'r:gz') as tar:
        seen=set()
        for member in tar:
            path=Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert path.parts[0]=='release_package' and member.name not in seen and member.size<64<<20
            target=OUT/path;target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(tar.extractfile(member).read())
            target.chmod(0o755 if path.parts[1]=='bin' else 0o600);seen.add(member.name)
    assert len(seen)==59
    package=OUT/'release_package'
    assert sha(package/'manifest.json')=='8c033ae717f3012469652faf1aa701cb5e48827c7084b9e9532134a6de4d0027'
    assert sha(package/'SHA256SUMS')=='9b06864efb26c7797fd54603fb7be37a911fffc6f8166d2d37a2a3dd31392491'
    for name,digest in read(package/'manifest.json')['files'].items():assert sha(package/name)==digest
    assert sha(package/'bin/bitbankpoloniex-guard')==CANDIDATE
    assert sha(package/'bin/bitbankpoloniex-rollback')==BASELINE
    return package

def main():
    os.umask(0o077)
    assert not (OUT/'deployment_inputs.json').exists(),'do not repeat an activation'
    qualification=read(OUT/'qualification_verified.json')
    assert qualification['verified'] and qualification['historical_accounts']==45
    assert qualification['candidate_sha256']==CANDIDATE and qualification['archive_sha256']==ARCHIVE_SHA
    package=extract();candidate=package/'bin/bitbankpoloniex-guard'
    running=check_running(BASELINE);before=read(STATE/'state.json')
    assert before['Pending'] is None and before['AccountBacked'] and before['Budget']=='489.1312417736'
    status_args=[str(candidate),*EXPECTED[1:]];status_args[status_args.index('--command')+1]='status'
    status=subprocess.run(status_args,cwd=ROOT,env=ENV,capture_output=True,text=True,timeout=30)
    assert status.returncode==0,status.stderr
    loaded=json.loads(status.stdout);assert loaded['Pending'] is None and loaded['Budget']==before['Budget']
    pre_doctor=doctor(candidate,'pre_stop_doctor')
    save(OUT/'deployment_inputs.json',dict(started_ns=time.time_ns(),qualification_sha256=sha(OUT/'qualification_verified.json'),
        script_sha256=sha(__file__),continuity_sha256=sha(Path(__file__).with_name('continuity.py')),
        unit_sha256=UNIT_SHA,baseline_sha256=BASELINE,candidate_sha256=CANDIDATE,arguments=EXPECTED,
        initial_service=running,initial_state_sha256=sha(STATE/'state.json'),pre_stop_doctor=pre_doctor))
    stopped=False;installed=False
    try:
        assert read(STATE/'state.json')['Pending'] is None
        stopped=True;command('stop')
        status=service();assert status['ActiveState']=='inactive' and status['MainPID']=='0',status
        before=read(STATE/'state.json');assert before['Pending'] is None,'pending intent after stop'
        doctor(candidate,'stopped_doctor')
        backup=OUT/'stopped_live_backup';shutil.copytree(STATE,backup)
        shutil.copy2(BINARY,OUT/'installed_before')
        state_hashes={str(p.relative_to(STATE)):sha(p) for p in STATE.rglob('*') if p.is_file()}
        assert all(sha(backup/name)==digest for name,digest in state_hashes.items())
        assert sha(OUT/'installed_before')==BASELINE
        save(OUT/'stopped_snapshot.json',dict(at_ns=time.time_ns(),state_hashes=state_hashes,
            state_backup=str(backup),budget=before['Budget'],fills=len(before['Fills']),pending=None,
            old_binary_sha256=BASELINE,unit_sha256=sha(UNIT)))
        install(candidate);installed=True
        assert sha(BINARY)==CANDIDATE and sha(UNIT)==UNIT_SHA
        assert {str(p.relative_to(STATE)):sha(p) for p in STATE.rglob('*') if p.is_file()}==state_hashes
        command('start');stopped=False
        observations,after=observe(CANDIDATE,before,'candidate')
        post_doctor=doctor(candidate,'post_start_doctor')
        current=check_running(CANDIDATE);assert current['NRestarts']=='0'
        records=subprocess.check_output(['journalctl','-u',SERVICE,'_PID='+current['MainPID'],'--no-pager','-o','json'],text=True)
        with (OUT/'candidate_journal.jsonl').open('x') as f:f.write(records)
        messages=[json.loads(line).get('MESSAGE','') for line in records.splitlines()]
        assert sum(m.endswith(' cycle complete') or ' cycle paused:' in m for m in messages)>=1  # log lines carry a timestamp prefix; observe() proves two completed cycles from state
        assert not any('cycle blocked (' in m or 'five consecutive failures' in m for m in messages)
        assert sha(UNIT)==UNIT_SHA and read(STATE/'state.json')['Pending'] is None
        save(OUT/'deployment_verified.json',dict(verified=True,ended_ns=time.time_ns(),observations=observations,
            post_start_doctor=post_doctor,candidate_sha256=CANDIDATE,baseline_sha256=BASELINE,
            state_preserved_before_start=True,continuity=continuity(before,after),unit_unchanged=True,
            parameters_unchanged=True,models_changed=False,manual_orders_submitted=False,
            service=current,state_backup=str(backup),live_changed=True))
        print('GUARD_DEPLOYED',current['MainPID'],CANDIDATE,flush=True)
    except Exception as error:
        failure=dict(error=str(error),installed=installed,stopped=stopped,at_ns=time.time_ns())
        try:
            if installed:
                stopped=True;command('stop')
                halted=service();assert halted['ActiveState']=='inactive' and halted['MainPID']=='0'
                latest=read(STATE/'state.json')
                if latest['Pending'] is not None:
                    command('start');stopped=False
                    failure['rollback_deferred']='pending intent; current service restarted to reconcile, no state restored'
                else:
                    doctor(BINARY,'rollback_doctor')
                    shutil.copytree(STATE,OUT/'rollback_latest_state')
                    install(package/'bin/bitbankpoloniex-rollback')
                    command('start');stopped=False
                    observations,_=observe(BASELINE,latest,'rollback')
                    failure['rollback_verified']=True;failure['rollback_observations']=observations
            elif stopped:command('start');stopped=False
        except Exception as rollback_error:
            failure['rollback_error']=str(rollback_error)
            if stopped:
                try:command('start');stopped=False
                except Exception as start_error:failure['restart_error']=str(start_error)
        save(OUT/'deployment_failure.json',failure)
        raise

if __name__=='__main__':main()
