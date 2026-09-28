from __future__ import annotations
import os
from pathlib import Path
from collections import Counter

SKIP={'.git','.codex','node_modules','__pycache__','.gradle','build','dist','target','.venv','venv'}
SECRET_NAMES={'.env','.env.local','.env.production','.npmrc','.pypirc','credentials.json','secrets.json'}
LANG={
'.py':'Python','.js':'JavaScript','.ts':'TypeScript','.tsx':'TSX','.jsx':'JSX','.java':'Java','.kt':'Kotlin','.kts':'Kotlin/Gradle','.gradle':'Gradle','.html':'HTML','.css':'CSS','.scss':'SCSS','.xml':'XML','.json':'JSON','.yaml':'YAML','.yml':'YAML','.go':'Go','.rs':'Rust','.c':'C','.h':'C/C++','.cpp':'C++','.cs':'C#','.swift':'Swift','.dart':'Dart','.php':'PHP','.rb':'Ruby','.lua':'Lua','.sql':'SQL','.sh':'Shell','.ps1':'PowerShell','.groovy':'Groovy','.scala':'Scala','.sol':'Solidity','.vue':'Vue','.svelte':'Svelte','.md':'Markdown'}

class ProjectIndex:
    def __init__(self, root: str): self.root=Path(root).resolve(); self.data={}
    def scan(self)->dict:
        files=dirs=0; sizes=0; langs=Counter(); configs=[]; samples=[]
        for base, dnames, fnames in os.walk(self.root):
            dnames[:] = [d for d in dnames if d not in SKIP and not d.startswith('.')]
            dirs += len(dnames)
            relbase=Path(base).relative_to(self.root)
            for name in fnames:
                p=Path(base)/name; files+=1
                try: sizes+=p.stat().st_size
                except OSError: pass
                if name in SECRET_NAMES or any(x in name.lower() for x in ('password','credential','token','secret')): continue
                lang=LANG.get(p.suffix.lower())
                if lang: langs[lang]+=1
                if name.lower() in {'package.json','pyproject.toml','requirements.txt','pom.xml','build.gradle','settings.gradle','settings.gradle.kts','build.gradle.kts','cargo.toml','go.mod','composer.json','pubspec.yaml','dockerfile'}: configs.append(str(p.relative_to(self.root)))
            if len(samples)<10 and fnames:
                for name in fnames:
                    p=Path(base)/name
                    if p.name in SECRET_NAMES: continue
                    if p.suffix.lower() in LANG and p.stat().st_size<12000:
                        try:
                            text=p.read_text(encoding='utf-8')[:1200]
                            samples.append({'path':str(p.relative_to(self.root)),'content':text})
                        except Exception: pass
        self.data={'root':str(self.root),'files':files,'directories':dirs,'bytes':sizes,'languages':dict(langs),'configs':configs[:80],'samples':samples[:10]}
        return self.data
    def compact_context(self)->str:
        if not self.data: self.scan()
        d=self.data
        lines=[f"Workspace: {d['root']}",f"Files: {d['files']}; directories: {d['directories']}; bytes: {d['bytes']}","Languages: "+(', '.join(f"{k}={v}" for k,v in sorted(d['languages'].items())) or 'none')]
        if d['configs']: lines.append('Build/config files: '+', '.join(d['configs'][:30]))
        if d['samples']:
            lines.append('Representative files: '+', '.join(x['path'] for x in d['samples']))
        # Give the model useful project knowledge, not only filenames. Keep it bounded
        # and prioritize documentation/config/entrypoints while avoiding secrets.
        priority = []
        preferred = {
            'README.md','README','pyproject.toml','package.json','Cargo.toml','go.mod',
            'requirements.txt','pom.xml','build.gradle','settings.gradle','Dockerfile',
            'docker-compose.yml','docker-compose.yaml'
        }
        for rel in d.get('configs', []):
            if Path(rel).name in preferred:
                priority.append(rel)
        for sample in d.get('samples', []):
            rel = sample['path']
            name = Path(rel).name
            if name in preferred or Path(rel).suffix.lower() in {'.py','.js','.ts','.tsx','.jsx','.go','.rs','.java','.kt','.html'}:
                priority.append(rel)
        seen=set(); selected=[]
        for rel in priority:
            if rel not in seen:
                seen.add(rel); selected.append(rel)
            if len(selected) >= 8: break
        if selected:
            lines.append('KEY PROJECT FILE CONTENT:')
            for rel in selected:
                p=self.root/rel
                try:
                    text=p.read_text(encoding='utf-8')
                except Exception:
                    continue
                if len(text)>3500: text=text[:3500]+'\n...[truncated]...'
                lines.append(f'--- {rel} ---\n{text}')
        return '\n'.join(lines)
