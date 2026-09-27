from __future__ import annotations
import difflib
import glob as globlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable
from .project import ProjectIndex
from .memory import MemoryStore
from .gitops import status as git_status, diff as git_diff, log as git_log
from .checkpoint import Checkpoints
from .doctor import run as doctor_run
from .jobs import JobStore

class ToolError(RuntimeError):
    pass

class Workspace:
    def __init__(self, root: str):
        self.root = Path(root).resolve()

    def path(self, value: str) -> Path:
        candidate = (self.root / value).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ToolError("Path berada di luar workspace.") from exc
        return candidate

def _read_pdf(path: Path) -> str:
    # PDF parsing is intentionally dependency-free. If pdftotext exists,
    # use it; otherwise return useful metadata rather than fake extracted text.
    exe = shutil.which("pdftotext")
    if exe:
        proc = subprocess.run(
            [exe, str(path), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0:
            return proc.stdout
    return f"[PDF: {path.name}; install poppler/pdftotext for text extraction]"

def read_file(ws: Workspace, path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    p = ws.path(path)
    if not p.exists():
        raise ToolError(f"File tidak ditemukan: {path}")
    if p.is_dir():
        raise ToolError("read membutuhkan file, bukan direktori.")
    if p.suffix.lower() == ".pdf":
        content = _read_pdf(p)
    else:
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            size = p.stat().st_size
            return f"[Binary file: {p.name}, {size} bytes]"
    if start_line is not None or end_line is not None:
        lines = content.splitlines()
        start = max((start_line or 1) - 1, 0)
        end = end_line if end_line is not None else len(lines)
        content = "\n".join(
            f"{i + 1}: {line}" for i, line in enumerate(lines[start:end], start)
        )
    return content

def write_file(ws: Workspace, path: str, content: str) -> str:
    p = ws.path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"wrote {path} ({len(content.encode())} bytes)"

def edit_file(ws: Workspace, path: str, old: str, new: str, count: int | None = None) -> str:
    p = ws.path(path)
    if not p.exists():
        raise ToolError(f"File tidak ditemukan: {path}")
    content = p.read_text(encoding="utf-8")
    occurrences = content.count(old)
    if occurrences == 0:
        raise ToolError("String target tidak ditemukan.")
    if count is None:
        count = occurrences
    if count < 1 or count > occurrences:
        raise ToolError(f"count harus 1..{occurrences}.")
    updated = content.replace(old, new, count)
    p.write_text(updated, encoding="utf-8")
    return f"edited {path}; replacements={count}"

def apply_patch(ws: Workspace, path: str, diff_text: str) -> str:
    p = ws.path(path)
    original = p.read_text(encoding="utf-8") if p.exists() else ""
    lines = original.splitlines(keepends=True)
    patch_lines = diff_text.splitlines(keepends=True)

    # Accept unified diffs containing a single file section.
    if patch_lines and patch_lines[0].startswith("--- "):
        patch_lines = patch_lines[2:] if len(patch_lines) >= 2 else []
    hunks = [line for line in patch_lines if line.startswith("@@")]
    if not hunks:
        raise ToolError("Patch harus berupa unified diff.")

    # Conservative application using system patch if available.
    patch_exe = shutil.which("patch")
    if patch_exe:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fh:
            fh.write(diff_text)
            patch_file = fh.name
        try:
            proc = subprocess.run(
                [patch_exe, "--batch", "--forward", str(p)],
                input=diff_text,
                text=True,
                capture_output=True,
                timeout=30,
            )
            if proc.returncode == 0:
                return f"patched {path}"
            raise ToolError(proc.stderr.strip() or proc.stdout.strip() or "patch gagal")
        finally:
            try:
                os.unlink(patch_file)
            except OSError:
                pass

    raise ToolError("Perintah `patch` tidak tersedia di Termux.")

def grep(ws: Workspace, pattern: str, path: str = ".", flags: str = "") -> str:
    root = ws.path(path)
    rg = shutil.which("rg")
    if rg:
        cmd = [rg, "--line-number", "--hidden", "--glob", "!.git"]
        if "i" in flags:
            cmd.append("-i")
        cmd += [pattern, str(root)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        output = proc.stdout or proc.stderr
        if not output:
            return output
        normalized = []
        root_prefix = str(ws.root) + os.sep
        for line in output.splitlines():
            normalized.append(line.replace(root_prefix, '', 1))
        return "\n".join(normalized)
    compiled = re.compile(pattern, re.I if "i" in flags else 0)
    results = []
    files = [root] if root.is_file() else root.rglob("*")
    for p in files:
        if not p.is_file() or ".git" in p.parts:
            continue
        try:
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if compiled.search(line):
                    results.append(f"{p.relative_to(ws.root)}:{n}:{line}")
        except (UnicodeDecodeError, OSError):
            continue
    return "\n".join(results)

def glob_files(ws: Workspace, pattern: str, path: str = ".") -> list[str]:
    base = ws.path(path)
    matches = globlib.glob(str(base / pattern), recursive=True)
    return [str(Path(m).resolve().relative_to(ws.root)) for m in matches]

def list_dir(ws: Workspace, path: str = ".", pattern: str = "*") -> list[str]:
    base = ws.path(path)
    return [str(p.relative_to(ws.root)) for p in sorted(base.glob(pattern))]

def bash(ws: Workspace, command: str, cwd: str = ".", timeout: int = 120) -> dict[str, Any]:
    working = ws.path(cwd)
    proc = subprocess.run(
        command,
        shell=True,
        cwd=working,
        capture_output=True,
        text=True,
        timeout=max(1, min(timeout, 900)),
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }

def webfetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 Codex-Termux-Agent"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")

def websearch(query: str, max_results: int = 8) -> list[dict[str, str]]:
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": query})
    html = webfetch(url)
    # DuckDuckGo result anchors are deliberately parsed with stdlib HTMLParser.
    from html.parser import HTMLParser
    class Parser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.results = []
            self.current = None
            self.capture = False
        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "a" and "result__a" in attrs.get("class", ""):
                self.current = {"url": attrs.get("href", ""), "title": ""}
                self.capture = True
        def handle_data(self, data):
            if self.current and self.capture:
                self.current["title"] += data.strip()
        def handle_endtag(self, tag):
            if tag == "a" and self.current:
                if self.current["title"]:
                    self.results.append(self.current)
                self.current = None
                self.capture = False
    parser = Parser()
    parser.feed(html)
    return parser.results[:max_results]

class TodoStore:
    def __init__(self):
        self.items: list[dict[str, Any]] = []
    def run(self, action: str, items: list[Any] | None = None) -> Any:
        if action == "read":
            return self.items
        if action == "write":
            self.items = [{"text": str(x), "done": False} for x in (items or [])]
            return self.items
        if action == "add":
            for x in items or []:
                self.items.append({"text": str(x), "done": False})
            return self.items
        if action == "done":
            index = int(items[0])
            self.items[index]["done"] = True
            return self.items
        if action == "clear":
            self.items = []
            return self.items
        raise ToolError(f"Aksi todo tidak dikenal: {action}")



def verify_project(ws: Workspace, command: str = "") -> dict[str, Any]:
    """Run a project verification command, auto-detecting common test commands when omitted."""
    root = ws.root
    if command.strip():
        cmd = command.strip()
    elif (root / "pyproject.toml").exists() or (root / "pytest.ini").exists() or (root / "tests").is_dir():
        cmd = "python -m pytest -q" if shutil.which("pytest") else "python -m unittest discover -v"
    elif (root / "package.json").exists():
        cmd = "npm test -- --runInBand"
    elif (root / "build.gradle").exists() or (root / "gradlew").exists():
        cmd = "./gradlew test" if (root / "gradlew").exists() else "gradle test"
    elif (root / "Cargo.toml").exists():
        cmd = "cargo test"
    elif (root / "go.mod").exists():
        cmd = "go test ./..."
    else:
        cmd = "python -m compileall -q ."
    proc = subprocess.run(cmd, cwd=root, shell=True, capture_output=True, text=True, timeout=180)
    return {"command": cmd, "returncode": proc.returncode, "ok": proc.returncode == 0,
            "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-12000:]}


def project_diff(ws: Workspace) -> str:
    """Return a readable working-tree diff, with a fallback for non-git projects."""
    if not (ws.root / ".git").exists():
        return "Not a Git repository; use read/write/patch results for file changes."
    proc = subprocess.run(["git", "diff", "--", "."], cwd=ws.root, capture_output=True, text=True, timeout=60)
    return proc.stdout or "(working tree has no unstaged diff)"

class ToolRegistry:
    def __init__(self, workspace: str):
        self.ws = Workspace(workspace)
        self.todo = TodoStore()
        self.memory = MemoryStore(workspace)
        self.project = ProjectIndex(workspace)
        self.checkpoints = Checkpoints(workspace)
        self.jobs = JobStore()
        self.config = None

    def specs(self) -> list[dict[str, Any]]:
        return [
            {"name":"read","description":"Read a workspace file; supports optional line range.","parameters":{"path":"string","start_line":"integer|null","end_line":"integer|null"}},
            {"name":"write","description":"Create or overwrite a workspace file.","parameters":{"path":"string","content":"string"}},
            {"name":"edit","description":"Replace exact text in a workspace file.","parameters":{"path":"string","old":"string","new":"string","count":"integer|null"}},
            {"name":"patch","description":"Apply a unified diff to a workspace file.","parameters":{"path":"string","diff":"string"}},
            {"name":"grep","description":"Regex search through workspace content.","parameters":{"pattern":"string","path":"string","flags":"string"}},
            {"name":"glob","description":"Find workspace paths using a glob pattern.","parameters":{"pattern":"string","path":"string"}},
            {"name":"list","description":"List workspace directory entries.","parameters":{"path":"string","pattern":"string"}},
            {"name":"bash","description":"Execute a shell command in Termux workspace.","parameters":{"command":"string","cwd":"string","timeout":"integer"}},
            {"name":"webfetch","description":"Fetch a URL.","parameters":{"url":"string","timeout":"integer"}},
            {"name":"websearch","description":"Search DuckDuckGo HTML.","parameters":{"query":"string","max_results":"integer"}},
            {"name":"todo","description":"Manage session tasks.","parameters":{"action":"read|write|add|done|clear","items":"array"}},
            {"name":"task","description":"Delegate a focused subtask to the same model.","parameters":{"prompt":"string","role":"string"}},
            {"name":"lsp","description":"Use an available language-server command for diagnostics/analysis.","parameters":{"action":"check|symbols|definition","path":"string","language":"string"}},
            {"name":"project_scan","description":"Scan and summarize the active project before coding.","parameters":{}},
            {"name":"memory","description":"Search or save persistent project/session memory.","parameters":{"action":"search|add|recent","query":"string","kind":"string","content":"string"}},
            {"name":"git","description":"Inspect Git status, diff, or recent log without changing repository state.","parameters":{"action":"status|diff|staged_diff|log","count":"integer"}},
            {"name":"checkpoint","description":"Create, list, or restore a local project checkpoint.","parameters":{"action":"create|list|restore","name":"string","label":"string"}},
            {"name":"doctor","description":"Diagnose Codex, workspace, tools, and environment health.","parameters":{}},
            {"name":"background","description":"Run a safe read/analysis subtask in the background and inspect its status later.","parameters":{"action":"start|list|get","prompt":"string","job_id":"string"}},
            {"name":"verify","description":"Run project tests/build/compile verification; auto-detect a suitable command when omitted.","parameters":{"command":"string"}},
            {"name":"diff","description":"Show the current Git working-tree diff for review before reporting changes.","parameters":{}},
            {"name":"goal","description":"Read or record the current project goal and acceptance notes in persistent memory.","parameters":{"action":"read|set","content":"string"}},
        ]

    def call(self, name: str, args: dict[str, Any], subagent: Callable[[str, str], str] | None = None) -> Any:
        if name == "read": return read_file(self.ws, args["path"], args.get("start_line"), args.get("end_line"))
        if name == "write": return write_file(self.ws, args["path"], args["content"])
        if name == "edit": return edit_file(self.ws, args["path"], args["old"], args["new"], args.get("count"))
        if name == "patch": return apply_patch(self.ws, args["path"], args["diff"])
        if name == "grep": return grep(self.ws, args["pattern"], args.get("path", "."), args.get("flags", ""))
        if name == "glob": return glob_files(self.ws, args["pattern"], args.get("path", "."))
        if name == "list": return list_dir(self.ws, args.get("path", "."), args.get("pattern", "*"))
        if name == "bash": return bash(self.ws, args["command"], args.get("cwd", "."), args.get("timeout", 120))
        if name == "webfetch": return webfetch(args["url"], args.get("timeout", 30))
        if name == "websearch": return websearch(args["query"], args.get("max_results", 8))
        if name == "todo": return self.todo.run(args["action"], args.get("items"))
        if name == "task":
            if subagent is None: raise ToolError("Subagent handler belum tersedia.")
            return subagent(args["prompt"], args.get("role", "general"))
        if name == "lsp":
            return self._lsp(args)
        if name == "project_scan":
            return self.project.scan()
        if name == "memory":
            action=args.get("action","search")
            if action == "search": return self.memory.search(args.get("query",""), 10)
            if action == "recent": return self.memory.recent(12)
            if action == "add": self.memory.add(args.get("kind","note"), args.get("content","")); return {"saved":True}
            raise ToolError("memory action tidak dikenal")
        if name == "git":
            action=args.get("action","status")
            if action == "status": return git_status(str(self.ws.root))
            if action == "diff": return git_diff(str(self.ws.root), False)
            if action == "staged_diff": return git_diff(str(self.ws.root), True)
            if action == "log": return git_log(str(self.ws.root), args.get("count",10))
            raise ToolError("git action tidak dikenal")
        if name == "checkpoint":
            action=args.get("action","list")
            if action == "create": return {"path":self.checkpoints.create(args.get("label","auto"))}
            if action == "list": return self.checkpoints.list()
            if action == "restore": return {"restored":self.checkpoints.restore(args["name"])}
            raise ToolError("checkpoint action tidak dikenal")
        if name == "doctor":
            return doctor_run(str(self.ws.root), self.config, self)
        if name == "verify":
            return verify_project(self.ws, args.get("command", ""))
        if name == "diff":
            return project_diff(self.ws)
        if name == "goal":
            action=args.get("action", "read")
            if action == "set":
                content=args.get("content", "").strip()
                if not content: raise ToolError("Goal tidak boleh kosong.")
                self.memory.add("goal", content, {"workspace": str(self.ws.root)})
                return {"saved": True, "goal": content}
            rows=[r for r in self.memory.recent(50) if r.get("kind") == "goal"]
            return rows[-8:]
        if name == "background":
            action=args.get("action","list")
            if action == "list": return self.jobs.list()
            if action == "get": return self.jobs.get(args.get("job_id","")) or {"error":"job tidak ditemukan"}
            if action == "start":
                if subagent is None: raise ToolError("Subagent handler belum tersedia.")
                prompt=args.get("prompt","")
                return self.jobs.start(lambda: subagent(prompt,"background analysis"), "AI background task")
            raise ToolError("background action tidak dikenal")
        raise ToolError(f"Tool tidak dikenal: {name}")

    def _lsp(self, args: dict[str, Any]) -> Any:
        path = self.ws.path(args["path"])
        action = args.get("action", "check")
        language = args.get("language", "")
        candidates = []
        if language in {"python", "py"}:
            candidates = [["pyright-langserver", "--stdio"], ["pylsp"]]
        elif language in {"typescript", "javascript", "ts", "js"}:
            candidates = [["typescript-language-server", "--stdio"]]
        for cmd in candidates:
            if shutil.which(cmd[0]):
                return {
                    "available": True,
                    "server": cmd[0],
                    "action": action,
                    "path": str(path.relative_to(self.ws.root)),
                    "note": "LSP server terdeteksi; sesi protokol penuh memerlukan client JSON-RPC.",
                }
        return {
            "available": False,
            "action": action,
            "path": str(path.relative_to(self.ws.root)),
            "message": "Language server yang cocok tidak ditemukan.",
        }
