from __future__ import annotations
import hashlib
import json, os, re, time
from pathlib import Path
from typing import Any

class MemoryStore:
    def __init__(self, workspace: str, max_records: int = 2000):
        self.root = Path(workspace).resolve()
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
        project_id = hashlib.sha256(str(self.root).encode("utf-8")).hexdigest()[:20]
        self.dir = home / "projects" / project_id
        self.path = self.dir / "memory.jsonl"
        self.meta_path = self.dir / "project.json"
        self.max_records = max_records
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.meta_path.exists():
            self.meta_path.write_text(json.dumps({"workspace": str(self.root)}, ensure_ascii=False, indent=2), encoding="utf-8")

    def add(self, kind: str, content: str, meta: dict[str, Any] | None = None) -> None:
        record = {'ts': int(time.time()), 'kind': kind, 'content': str(content), 'meta': meta or {}}
        with self.path.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        self._trim()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists(): return []
        out=[]
        for line in self.path.read_text(encoding='utf-8', errors='replace').splitlines():
            try:
                obj=json.loads(line)
                if isinstance(obj, dict): out.append(obj)
            except json.JSONDecodeError: continue
        return out

    def _trim(self) -> None:
        rows=self._read()
        if len(rows) > self.max_records:
            rows=rows[-self.max_records:]
            self.path.write_text(''.join(json.dumps(x, ensure_ascii=False)+'\n' for x in rows), encoding='utf-8')

    def recent(self, n: int = 12) -> list[dict[str, Any]]:
        return self._read()[-n:]

    def search(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        q=set(re.findall(r'\w+', query.lower()))
        if not q: return self.recent(limit)
        scored=[]
        for row in self._read():
            text=(row.get('content','')+' '+json.dumps(row.get('meta',{}), ensure_ascii=False)).lower()
            words=set(re.findall(r'\w+', text))
            score=len(q & words)
            if score: scored.append((score, row))
        scored.sort(key=lambda x:(x[0], x[1].get('ts',0)), reverse=True)
        return [r for _,r in scored[:limit]]

    def context(self, query: str, limit: int = 6) -> str:
        # Combine semantic-ish keyword matches with a small recent tail so
        # recent tool results/decisions remain visible even when the current
        # wording does not share the same keywords. Deduplicate by timestamp/content.
        rows = self.search(query, limit)
        recent = self.recent(min(4, limit))
        merged=[]; seen=set()
        for r in rows + recent:
            key=(r.get('ts'), r.get('kind'), r.get('content'))
            if key in seen: continue
            seen.add(key); merged.append(r)
        if not merged: return ''
        lines=[]
        for r in merged[:limit+4]:
            content=r.get('content','').strip().replace('\n',' ')
            if len(content)>700: content=content[:700]+'…'
            lines.append(f"[{r.get('kind','memory')}] {content}")
        return '\n'.join(lines)
