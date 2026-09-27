from __future__ import annotations
import os
import re
import shutil
from dataclasses import dataclass

RESET = "\033[0m"; DIM = "\033[2m"; BOLD = "\033[1m"
CYAN = "\033[96m"; BLUE = "\033[94m"; GREEN = "\033[92m"
YELLOW = "\033[93m"; MAGENTA = "\033[95m"; RED = "\033[91m"; GRAY = "\033[90m"

# Markdown fences can be indented and may use backticks or tildes. Language is optional.
FENCE_RE = re.compile(r"(?ms)^[ \t]{0,3}(`{3,}|~{3,})[ \t]*([^\r\n`]*)\r?\n(.*?)(?:\r?\n)[ \t]{0,3}\1[ \t]*(?=\r?$|\r?\n)")
OPEN_FENCE_RE = re.compile(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[ \t]*([^\r\n`]*)\r?\n")

LANG_ALIASES = {
    "py":"python","python3":"python","js":"javascript","jsx":"javascript","mjs":"javascript","cjs":"javascript",
    "ts":"typescript","tsx":"typescript","sh":"bash","shell":"bash","zsh":"bash","yml":"yaml",
    "md":"markdown","text":"text","plaintext":"text","txt":"text","html5":"html","htm":"html",
    "xhtml":"html","xml":"xml","scss":"css","less":"css","ps1":"powershell","docker":"dockerfile",
    "c++":"cpp","cc":"cpp","h++":"cpp","cs":"csharp","golang":"go","rs":"rust","kt":"kotlin",
}

KEYWORDS = {
    "python": r"\b(def|class|import|from|as|if|elif|else|for|while|in|try|except|finally|with|return|yield|lambda|True|False|None|and|or|not|is|async|await|pass|raise|assert)\b",
    "javascript": r"\b(function|const|let|var|if|else|for|while|return|class|new|import|from|export|async|await|try|catch|throw|true|false|null|undefined)\b",
    "typescript": r"\b(function|const|let|var|if|else|for|while|return|class|new|import|from|export|async|await|try|catch|throw|true|false|null|undefined|interface|type|public|private)\b",
    "bash": r"\b(if|then|else|fi|for|while|in|do|done|case|esac|function|export|local|source|return)\b",
    "json": r'"(?:[^"\\]|\\.)*"(?=\s*:)',
    "yaml": r"^\s*[A-Za-z_][\w.-]*(?=:\s)",
    "html": r"</?[A-Za-z][^>]*>|<!DOCTYPE[^>]*>",
    "xml": r"</?[A-Za-z][^>]*>|<\?xml[^>]*\?>",
    "css": r"\b(margin|padding|display|position|color|background|font|width|height|grid|flex|border|content|align-items|justify-content)\b",
    "sql": r"\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|DELETE|CREATE|ALTER|DROP|JOIN|GROUP|ORDER|BY|LIMIT|AND|OR)\b",
    "java": r"\b(class|public|private|protected|static|void|new|return|if|else|for|while|extends|implements|import|package|true|false|null)\b",
    "kotlin": r"\b(fun|class|object|val|var|when|if|else|for|while|return|import|package|true|false|null|data|sealed)\b",
    "go": r"\b(package|import|func|type|struct|interface|return|if|else|for|range|go|defer|var|const|nil|true|false)\b",
    "rust": r"\b(fn|let|mut|struct|enum|impl|trait|use|mod|pub|return|match|if|else|for|while|loop|true|false|None|Some)\b",
    "cpp": r"\b(class|struct|namespace|include|using|public|private|protected|int|void|auto|return|if|else|for|while|const|new|delete|true|false|nullptr)\b",
    "c": r"\b(struct|typedef|include|define|int|char|void|return|if|else|for|while|const|static|NULL)\b",
    "csharp": r"\b(class|namespace|using|public|private|protected|static|void|var|new|return|if|else|for|foreach|while|true|false|null)\b",
    "php": r"\b(function|class|namespace|use|public|private|protected|return|if|else|foreach|while|echo|new|null|true|false)\b",
    "ruby": r"\b(def|class|module|require|include|if|elsif|else|end|do|while|until|return|true|false|nil)\b",
    "swift": r"\b(func|class|struct|enum|import|let|var|if|else|for|while|return|guard|switch|case|true|false|nil)\b",
    "dart": r"\b(void|class|import|final|const|var|late|if|else|for|while|return|async|await|true|false|null)\b",
    "powershell": r"\b(function|param|if|else|foreach|for|while|return|class|true|false|null)\b",
    "dockerfile": r"\b(FROM|RUN|CMD|ENTRYPOINT|COPY|ADD|WORKDIR|ENV|EXPOSE|USER|ARG|VOLUME)\b",
}


def normalize_language(raw: str) -> str:
    raw = (raw or "").strip().lower()
    if not raw:
        return "text"
    lang = raw.split()[0].strip("{}[](),")
    return LANG_ALIASES.get(lang, lang)


def detect_language(code: str, hint: str = "") -> str:
    hinted = normalize_language(hint)
    if hinted != "text":
        return hinted
    s = code.lstrip()
    low = s.lower()
    if re.search(r"<!doctype\s+html|<html(?:\s|>)|<head(?:\s|>)|<body(?:\s|>)", low): return "html"
    if re.search(r"<\?xml|</?[A-Za-z][^>]*>", s) and not re.search(r"=>|\bfunction\b", s): return "xml"
    if re.match(r"\s*[\[{]", s):
        try:
            import json
            json.loads(s); return "json"
        except Exception: pass
    if re.search(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b", s, re.I|re.M): return "sql"
    if re.search(r"(^|\n)\s*(body|html|:root|\.[\w-]+|#[\w-]+)\s*\{", s) and ":" in s: return "css"
    if re.search(r"(^|\n)\s*(import\s+|from\s+\w+\s+import|def\s+\w+|class\s+\w+.*:)", s): return "python"
    if re.search(r"\b(const|let|var)\s+\w+\s*=|console\.log\(|=>", s): return "javascript"
    if re.search(r"(^|\n)\s*(#!/.*\b(?:bash|sh)|echo\s+|if\s+\[|for\s+\w+\s+in\s+)", s): return "bash"
    if re.search(r"\bfn\s+\w+\s*\(|\blet\s+mut\s+", s): return "rust"
    if re.search(r"\bfunc\s+\w+\s*\(", s) and "package " in s: return "go"
    return "text"


def _highlight_line(line: str, language: str) -> str:
    pattern = KEYWORDS.get(language)
    if not pattern:
        return line
    parts = re.split(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#[^\n]*|//[^\n]*|\b\d+(?:\.\d+)?\b)', line)
    out = []
    for part in parts:
        if not part: continue
        if part.startswith(('"', "'")): out.append(GREEN + part + RESET)
        elif part.startswith("#") or part.startswith("//"): out.append(GRAY + part + RESET)
        elif re.fullmatch(r"\d+(?:\.\d+)?", part): out.append(YELLOW + part + RESET)
        else: out.append(re.sub(pattern, lambda m: MAGENTA + m.group(0) + RESET, part))
    return "".join(out)


def highlight_code(code: str, language: str) -> str:
    language = normalize_language(language)
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(_highlight_line(line, language) for line in code.rstrip("\n").split("\n"))


def _fold_lines(lines: list[str]) -> tuple[list[str], int]:
    try: limit = int(os.environ.get("CODEX_FOLD_LINES", "0"))
    except ValueError: limit = 0
    if limit <= 0 or len(lines) <= limit:
        return lines, 0
    head = max(20, limit - 20)
    tail = 20
    hidden = len(lines) - head - tail
    return lines[:head] + [f"{DIM}… {hidden} baris disembunyikan; set CODEX_FOLD_LINES=0 untuk menampilkan semua …{RESET}"] + lines[-tail:], hidden


def render_code_block(language: str, code: str) -> str:
    language = detect_language(code, language)
    width = min(shutil.get_terminal_size((80, 24)).columns, 110)
    raw_lines = code.replace("\r\n", "\n").replace("\r", "\n").rstrip("\n").split("\n") or [""]
    lines, _ = _fold_lines(raw_lines)
    number_width = max(2, len(str(len(raw_lines))))
    header_text = f" {language} · {len(raw_lines)} lines "
    header = f"{BLUE}{BOLD}┌─{header_text}{'─' * max(1, width - len(header_text) - 3)}┐{RESET}"
    rendered = [header]
    for idx, line in enumerate(lines, 1):
        shown_no = idx if not line.startswith(f"{DIM}…") else "·"
        rendered.append(f"{BLUE}│{RESET} {DIM}{str(shown_no).rjust(number_width)}{RESET} │ {highlight_code(line, language)}")
    rendered.append(f"{BLUE}└{'─' * max(1, width - 1)}┘{RESET}")
    return "\n".join(rendered)


def _render_fallback_unclosed(text: str) -> str:
    m = OPEN_FENCE_RE.search(text)
    if not m: return text
    code = text[m.end():]
    before = text[:m.start()].rstrip("\n")
    block = render_code_block(m.group(2), code)
    return (before + "\n\n" if before else "") + block


def render_markdown(text: str) -> str:
    if not text: return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    output=[]; pos=0
    for match in FENCE_RE.finditer(text):
        before=text[pos:match.start()].strip("\n")
        if before: output.append(before)
        output.append(render_code_block(match.group(2), match.group(3)))
        pos=match.end()
    tail=text[pos:].strip("\n")
    if tail:
        if OPEN_FENCE_RE.search(tail): output.append(_render_fallback_unclosed(tail))
        else: output.append(tail)
    return "\n\n".join(output) if output else _render_fallback_unclosed(text)


def extract_code_blocks(text: str) -> list[dict[str, str]]:
    """Extract fenced code blocks for clipboard/snippet workflows."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks=[]
    for i, match in enumerate(FENCE_RE.finditer(text), 1):
        code=match.group(3)
        hint=match.group(2)
        blocks.append({"index":str(i), "language":detect_language(code, hint), "code":code})
    if not blocks:
        m=OPEN_FENCE_RE.search(text)
        if m:
            blocks.append({"index":"1", "language":detect_language(text[m.end():], m.group(2)), "code":text[m.end():]})
    return blocks


@dataclass
class LiveMarkdownRenderer:
    """Stream prose immediately while buffering an open Markdown code fence."""
    printed: int = 0
    text: str = ""

    def feed(self, chunk: str) -> None:
        if not chunk: return
        self.text += chunk.replace("\r\n", "\n").replace("\r", "\n")
        # Find the last unmatched opening fence. Everything before it is stable.
        safe_end = self._safe_prefix_end(self.text)
        if safe_end > self.printed:
            import sys
            sys.stdout.write(self.text[self.printed:safe_end])
            sys.stdout.flush()
            self.printed = safe_end

    @staticmethod
    def _safe_prefix_end(text: str) -> int:
        # A fence that has not closed must remain buffered; otherwise the whole response is safe.
        opens=[]
        for m in re.finditer(r"(?m)^[ \t]{0,3}(`{3,}|~{3,})[ \t]*[^\r\n]*\r?\n", text):
            token=m.group(1)[0]; n=len(m.group(1))
            opens.append((m.start(), m.end(), token, n))
        for start,end,token,n in reversed(opens):
            close_re=re.compile(rf"(?m)^[ \\t]{{0,3}}{re.escape(token)}{{{n},}}[ \\t]*(?:$|\\n)")
            if not close_re.search(text, end):
                return start
        return len(text)

    def finish(self, final_text: str | None = None) -> None:
        if final_text is not None and len(final_text) >= len(self.text):
            self.text = final_text.replace("\r\n", "\n").replace("\r", "\n")
        import sys
        remainder=self.text[self.printed:]
        if remainder:
            sys.stdout.write(render_markdown(remainder))
            self.printed=len(self.text)
        sys.stdout.write("\n")
        sys.stdout.flush()
