from __future__ import annotations
import json, os, re, time
from pathlib import Path
from typing import Any

class MemoryStore:
    def __init__(self, workspace: str, max_records: int = 2000):
        self.root = Path(workspace).resolve()
        self.dir = self.root / '.codex'
        self.path = self.dir / 'memory.jsonl'
        self.max_records = max_records
        self.dir.mkdir(parents=True, exist_ok=True)

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
        rows=self.search(query, limit)
        if not rows: return ''
        lines=[]
        for r in rows:
            content=r.get('content','').strip().replace('\n',' ')
            if len(content)>700: content=content[:700]+'…'
            lines.append(f"[{r.get('kind','memory')}] {content}")
        return '\n'.join(lines)
