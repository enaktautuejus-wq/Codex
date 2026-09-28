from __future__ import annotations
import hashlib
import json, os, re, time, uuid
from pathlib import Path
from typing import Any

class MemoryStore:
    def __init__(self, workspace: str, max_records: int = 2000):
        self.root = Path(workspace).resolve()
        home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser().resolve()
        project_id = hashlib.sha256(str(self.root).encode("utf-8")).hexdigest()[:20]
        self.dir = home / "projects" / project_id
        self.path = self.dir / "memory.jsonl"
        self.sessions_dir = self.dir / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = uuid.uuid4().hex[:16]
        self.session_path = self.sessions_dir / f"{self.session_id}.jsonl"
        self.meta_path = self.dir / "project.json"
        self.max_records = max_records
        self.dir.mkdir(parents=True, exist_ok=True)
        if not self.meta_path.exists():
            self.meta_path.write_text(json.dumps({"workspace": str(self.root)}, ensure_ascii=False, indent=2), encoding="utf-8")
        # Keep session storage bounded; a new process/new /new creates a new session.
        try:
            sessions=sorted(self.sessions_dir.glob("*.jsonl"), key=lambda x:x.stat().st_mtime, reverse=True)
            for old in sessions[12:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass

    def add(self, kind: str, content: str, meta: dict[str, Any] | None = None) -> None:
        record = {'ts': int(time.time()), 'kind': kind, 'content': str(content), 'meta': meta or {}}
        # Conversation/tool events are session-scoped. Explicit durable kinds
        # survive /new and application restarts.
        durable = {'decision', 'fact', 'architecture', 'convention', 'known_issue', 'preference'}
        target = self.path if kind in durable else self.session_path
        with target.open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        self._trim_file(target)

    def _read_file(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists(): return []
        out=[]
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj=json.loads(line)
                if isinstance(obj, dict): out.append(obj)
            except json.JSONDecodeError: continue
        return out

    def _read_file(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists(): return []
        out=[]
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj=json.loads(line)
                if isinstance(obj, dict): out.append(obj)
            except json.JSONDecodeError: continue
        return out

    def _read_file(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists(): return []
        out=[]
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                obj=json.loads(line)
                if isinstance(obj, dict): out.append(obj)
            except json.JSONDecodeError: continue
        return out

    def _read(self) -> list[dict[str, Any]]:
        # Only explicit durable project knowledge from the global store and
        # the current session are visible. Legacy session records in the old
        # memory.jsonl are intentionally ignored.
        durable = {"decision", "fact", "architecture", "convention", "known_issue", "preference"}
        project = [r for r in self._read_file(self.path) if r.get("kind") in durable]
        return project + self._read_file(self.session_path)

    def _trim_file(self, path: Path) -> None:
        try:
            rows=self._read_file(path)
            if len(rows) > self.max_records:
                rows=rows[-self.max_records:]
                path.write_text("".join(json.dumps(x, ensure_ascii=False)+"\n" for x in rows), encoding="utf-8")
        except OSError:
            pass

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
