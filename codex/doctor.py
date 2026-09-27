from __future__ import annotations
import shutil, os, urllib.request
from pathlib import Path

def run(root: str, config=None, registry=None):
    checks=[]
    for cmd in ['python','git','rg','patch']:
        checks.append({'name':cmd,'ok':bool(shutil.which(cmd)),'detail':shutil.which(cmd) or 'tidak ditemukan'})
    checks.append({'name':'workspace','ok':Path(root).is_dir(),'detail':root})
    if config:
        checks.append({'name':'api config','ok':bool(config.api_key and config.model and config.endpoint),'detail':config.model})
    if registry:
        checks.append({'name':'tool registry','ok':len(registry.specs())>0,'detail':f'{len(registry.specs())} tools'})
    checks.append({'name':'memory','ok':(Path(root)/'.codex'/'memory.jsonl').parent.is_dir(),'detail':'.codex'})
    return {'ready':all(x['ok'] for x in checks if x['name'] not in {'rg','patch'}),'checks':checks}
