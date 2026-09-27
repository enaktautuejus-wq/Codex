from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import threading, uuid

class JobStore:
    def __init__(self):
        self.pool=ThreadPoolExecutor(max_workers=3); self.lock=threading.Lock(); self.jobs={}
    def start(self, fn, label='background'):
        jid=uuid.uuid4().hex[:8]
        with self.lock: self.jobs[jid]={'id':jid,'label':label,'status':'running','result':None}
        def run():
            try: result=fn(); state={'status':'done','result':result}
            except Exception as exc: state={'status':'failed','result':str(exc)}
            with self.lock: self.jobs[jid].update(state)
        self.pool.submit(run); return self.jobs[jid]
    def list(self):
        with self.lock: return list(self.jobs.values())
    def get(self,jid):
        with self.lock: return self.jobs.get(jid)
