from __future__ import annotations
import os
from pathlib import Path
from collections import Counter
import json, hashlib, re

SKIP={'.git','.codex','node_modules','__pycache__','.gradle','build','dist','target','.venv','venv'}
SECRET_NAMES={'.env','.env.local','.env.production','.npmrc','.pypirc','credentials.json','secrets.json'}
LANG={
'.py':'Python','.js':'JavaScript','.ts':'TypeScript','.tsx':'TSX','.jsx':'JSX','.java':'Java','.kt':'Kotlin','.kts':'Kotlin/Gradle','.gradle':'Gradle','.html':'HTML','.css':'CSS','.scss':'SCSS','.xml':'XML','.json':'JSON','.yaml':'YAML','.yml':'YAML','.go':'Go','.rs':'Rust','.c':'C','.h':'C/C++','.cpp':'C++','.cs':'C#','.swift':'Swift','.dart':'Dart','.php':'PHP','.rb':'Ruby','.lua':'Lua','.sql':'SQL','.sh':'Shell','.ps1':'PowerShell','.groovy':'Groovy','.scala':'Scala','.sol':'Solidity','.vue':'Vue','.svelte':'Svelte','.md':'Markdown'}

class ProjectIndex:
    def __init__(self, root: str):
        self.root=Path(root).resolve(); self.data={}
        home=Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex"))).expanduser()
        self.project_id=hashlib.sha256(str(self.root).encode()).hexdigest()[:20]
        self.cache_path=home/"projects"/self.project_id/"index.json"
    def scan(self)->dict:
        """Analyze the existing workspace in-place; never clone or modify the project."""
        files=dirs=0; sizes=0; langs=Counter(); configs=[]; samples=[]; entrypoints=[]; tree=[]
        config_names={
            'package.json','pyproject.toml','requirements.txt','pom.xml','build.gradle','settings.gradle',
            'settings.gradle.kts','build.gradle.kts','cargo.toml','go.mod','composer.json','pubspec.yaml',
            'dockerfile','makefile','cmakelists.txt','vite.config.js','vite.config.ts','tsconfig.json'
        }
        entry_names={
            'main.py','app.py','server.py','manage.py','index.js','index.ts','main.js','main.ts','main.kt',
            'application.kt','main.java','main.go','main.rs','main.dart','main.cpp','main.c','index.html'
        }
        for base, dnames, fnames in os.walk(self.root):
            dnames[:] = [d for d in dnames if d not in SKIP and not d.startswith('.')]
            relbase=Path(base).relative_to(self.root)
            if str(relbase) != '.': tree.append(str(relbase) + '/')
            dirs += len(dnames)
            for name in sorted(fnames):
                p=Path(base)/name; files+=1
                try: sizes+=p.stat().st_size
                except OSError: continue
                rel=str(p.relative_to(self.root))
                if len(tree)<240: tree.append(rel)
                low=name.lower()
                if name in SECRET_NAMES or any(x in low for x in ('password','credential','token','secret')): continue
                lang=LANG.get(p.suffix.lower())
                if lang: langs[lang]+=1
                if low in config_names: configs.append(rel)
                if low in entry_names or low.startswith('main.') or low.startswith('index.'):
                    entrypoints.append(rel)
                if len(samples)<18 and p.suffix.lower() in LANG and p.stat().st_size<16000:
                    try:
                        text=p.read_text(encoding='utf-8')[:1800]
                        samples.append({'path':rel,'content':text})
                    except Exception: pass
        # Prefer human/project intent files and actual entrypoints in the context.
        priority=[]
        for rel in ['README.md','README','AGENTS.md','CONTRIBUTING.md','package.json','pyproject.toml','build.gradle','settings.gradle','build.gradle.kts','settings.gradle.kts','Cargo.toml','go.mod','pubspec.yaml']:
            if (self.root/rel).is_file(): priority.append(rel)
        priority += entrypoints[:20]
        for sample in samples: priority.append(sample['path'])
        seen=set(); key_files=[]
        for rel in priority:
            if rel not in seen and (self.root/rel).is_file():
                seen.add(rel); key_files.append(rel)
        key_contents=[]
        for rel in key_files[:14]:
            try:
                text=(self.root/rel).read_text(encoding='utf-8')
                if len(text)>4200: text=text[:4200]+'\n...[truncated]...'
                key_contents.append({'path':rel,'content':text})
            except Exception: pass
        self.data={
            'root':str(self.root),'files':files,'directories':dirs,'bytes':sizes,
            'languages':dict(langs),'configs':configs[:80],'entrypoints':entrypoints[:40],
            'tree':tree[:240],'samples':samples[:18],'key_files':key_contents,
            'analysis_note':'Existing workspace analyzed directly; no clone/copy was performed.'
        }
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        except OSError: pass
        return self.data

    def relevant_context(self, query: str, limit: int = 6) -> str:
        if not self.data:
            self.scan()
        q=set(re.findall(r'[\w.-]+', (query or '').lower()))
        candidates=[]
        for sample in self.data.get('samples', []):
            path=sample.get('path','')
            content=sample.get('content','')
            words=set(re.findall(r'[\w.-]+', (path+' '+content).lower()))
            score=len(q & words)
            if score:
                candidates.append((score,path,content))
        candidates.sort(key=lambda x:(x[0],x[1]), reverse=True)
        if not candidates:
            return ''
        out=['RELEVANT PROJECT FILES FOR CURRENT REQUEST:']
        for _,path,content in candidates[:limit]:
            out.append(f'--- {path} ---\n{content[:2800]}')
        return '\n'.join(out)
    def compact_context(self)->str:
        if not self.data: self.scan()
        d=self.data
        lines=[f"Workspace: {d['root']}",f"Files: {d['files']}; directories: {d['directories']}; bytes: {d['bytes']}","Languages: "+(', '.join(f"{k}={v}" for k,v in sorted(d['languages'].items())) or 'none'),d.get('analysis_note','')]
        if d['configs']: lines.append('Build/config files: '+', '.join(d['configs'][:30]))
        if d.get('entrypoints'): lines.append('Likely entrypoints: '+', '.join(d['entrypoints'][:25]))
        if d.get('tree'): lines.append('Project tree (existing workspace):\n'+'\n'.join(d['tree'][:140]))
        if d['samples']: lines.append('Representative files: '+', '.join(x['path'] for x in d['samples']))
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
