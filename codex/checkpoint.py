from __future__ import annotations
import shutil, time
from pathlib import Path
class Checkpoints:
    def __init__(self, root: str):
        self.root=Path(root).resolve(); self.dir=self.root/'.codex'/'checkpoints'; self.dir.mkdir(parents=True,exist_ok=True)
    def create(self,label='auto'):
        stamp=time.strftime('%Y%m%d-%H%M%S'); dest=self.dir/f'{stamp}-{label.replace(" ","-")}'
        shutil.copytree(self.root,dest,ignore=shutil.ignore_patterns('.git','.codex','node_modules','__pycache__'),dirs_exist_ok=True)
        return str(dest)
    def list(self): return sorted(str(p.relative_to(self.dir)) for p in self.dir.iterdir() if p.is_dir())
    def restore(self,name):
        src=(self.dir/name).resolve()
        if not src.is_dir() or self.dir not in src.parents: raise ValueError('Checkpoint tidak valid')
        for p in self.root.iterdir():
            if p.name in {'.git','.codex'}: continue
            if p.is_dir(): shutil.rmtree(p)
            else: p.unlink()
        for p in src.iterdir():
            target=self.root/p.name
            if p.is_dir(): shutil.copytree(p,target)
            else: shutil.copy2(p,target)
        return str(src)
