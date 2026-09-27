from __future__ import annotations
import subprocess
from pathlib import Path

def _run(root: str, args: list[str], timeout=30):
    p=subprocess.run(['git','-C',root,*args],capture_output=True,text=True,timeout=timeout)
    return {'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def status(root): return _run(root,['status','--short','--branch'])
def diff(root, staged=False): return _run(root,['diff'] + (['--staged'] if staged else []),60)
def log(root, n=10): return _run(root,['log',f'-{max(1,min(n,50))}','--oneline','--decorate'],30)
