from __future__ import annotations
import os
import re
import shutil
from dataclasses import dataclass

RESET = "\033[0m"; DIM = "\033[2m"; BOLD = "\033[1m"
CYAN = "\033[96m"; BLUE = "\033[94m"; GREEN = "\033[92m"
YELLOW = "\033[93m"; MAGENTA = "\033[95m"; RED = "\033[91m"; GRAY = "\033[90m"

LANG_ALIASES = {
    "py":"python","python3":"python","js":"javascript","jsx":"javascript","mjs":"javascript","cjs":"javascript",
    "ts":"typescript","tsx":"typescript","sh":"bash","shell":"bash","zsh":"bash","yml":"yaml",
    "md":"markdown","text":"text","plaintext":"text","txt":"text","html5":"html","htm":"html",
    "xhtml":"html","xml":"xml","scss":"css","less":"css","ps1":"powershell","docker":"dockerfile",
    "c++":"cpp","cc":"cpp","h++":"cpp","cs":"csharp","golang":"go","rs":"rust","kt":"kotlin",
    "kts":"kotlin","gradle":"gradle","gradle.kts":"gradle","vue":"vue","svelte":"svelte",
}

KEYWORDS = {
    "python": r"\b(def|class|import|from|as|if|elif|else|for|while|in|try|except|finally|with|return|yield|lambda|True|False|None|and|or|not|is|async|await|pass|raise|assert|match|case)\b",
    "javascript": r"\b(function|const|let|var|if|else|for|while|return|class|new|import|from|export|async|await|try|catch|throw|true|false|null|undefined|switch|case|break|continue)\b",
    "typescript": r"\b(function|const|let|var|if|else|for|while|return|class|new|import|from|export|async|await|try|catch|throw|true|false|null|undefined|interface|type|public|private|readonly|enum|implements)\b",
    "bash": r"\b(if|then|else|fi|for|while|in|do|done|case|esac|function|export|local|source|return|echo)\b",
    "java": r"\b(class|public|private|protected|static|void|new|return|if|else|for|while|extends|implements|import|package|true|false|null|final|interface)\b",
    "kotlin": r"\b(fun|class|object|val|var|when|if|else|for|while|return|import|package|true|false|null|data|sealed|interface|override)\b",
    "go": r"\b(package|import|func|type|struct|interface|return|if|else|for|range|go|defer|var|const|nil|true|false|map|chan)\b",
    "rust": r"\b(fn|let|mut|struct|enum|impl|trait|use|mod|pub|return|match|if|else|for|while|loop|true|false|None|Some|crate|async|await)\b",
    "cpp": r"\b(class|struct|namespace|include|using|public|private|protected|int|void|auto|return|if|else|for|while|const|new|delete|true|false|nullptr|template)\b",
    "c": r"\b(struct|typedef|include|define|int|char|void|return|if|else|for|while|const|static|NULL|enum)\b",
    "csharp": r"\b(class|namespace|using|public|private|protected|static|void|var|new|return|if|else|for|foreach|while|true|false|null|async|await)\b",
    "php": r"\b(function|class|namespace|use|public|private|protected|return|if|else|foreach|while|echo|new|null|true|false)\b",
    "ruby": r"\b(def|class|module|require|include|if|elsif|else|end|do|while|until|return|true|false|nil)\b",
    "swift": r"\b(func|class|struct|enum|import|let|var|if|else|for|while|return|guard|switch|case|true|false|nil|protocol)\b",
    "dart": r"\b(void|class|import|final|const|var|late|if|else|for|while|return|async|await|true|false|null|extends|implements)\b",
    "powershell": r"\b(function|param|if|else|foreach|for|while|return|class|true|false|null|begin|process|end)\b",
    "sql": r"\b(SELECT|FROM|WHERE|INSERT|INTO|VALUES|UPDATE|DELETE|CREATE|ALTER|DROP|JOIN|GROUP|ORDER|BY|LIMIT|AND|OR|AS|ON|SET)\b",
    "dockerfile": r"\b(FROM|RUN|CMD|ENTRYPOINT|COPY|ADD|WORKDIR|ENV|EXPOSE|USER|ARG|VOLUME|LABEL)\b",
    "gradle": r"\b(plugins|id|version|group|repositories|dependencies|implementation|api|testImplementation|android|kotlin|tasks|build|project)\b",
    "css": r"\b(margin|padding|display|position|color|background|font|width|height|grid|flex|border|content|align-items|justify-content|transform|transition)\b",
}

OPEN_RE = re.compile(r"(?m)^[ \t]{0,8}(`{3,}|~{3,})([^\r\n]*)\r?\n")


def normalize_language(raw: str) -> str:
    raw = (raw or "").strip().lower()
    if not raw: return "text"
    lang = raw.split()[0].strip("{}[](),")
    return LANG_ALIASES.get(lang, lang)


def detect_language(code: str, hint: str = "") -> str:
    hinted = normalize_language(hint)
    if hinted != "text": return hinted
    s = code.lstrip(); low = s.lower()
    if re.search(r"<!doctype\s+html|<html(?:\s|>)|<head(?:\s|>)|<body(?:\s|>)", low): return "html"
    if re.search(r"<\?xml|</?[A-Za-z][^>]*>", s) and not re.search(r"=>|\bfunction\b", s): return "xml"
    if re.match(r"\s*[\[{]", s):
        try:
            import json; json.loads(s); return "json"
        except Exception: pass
    if re.search(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b", s, re.I|re.M): return "sql"
    if re.search(r"(^|\n)\s*(body|html|:root|\.[\w-]+|#[\w-]+)\s*\{", s) and ":" in s: return "css"
    if re.search(r"(^|\n)\s*(import\s+|from\s+\w+\s+import|def\s+\w+|class\s+\w+.*:)", s): return "python"
    if re.search(r"\b(const|let|var)\s+\w+\s*=|console\.log\(|=>", s): return "javascript"
    if re.search(r"(^|\n)\s*(#!/.*\b(?:bash|sh)|echo\s+|if\s+\[|for\s+\w+\s+in\s+)", s): return "bash"
    if re.search(r"\bfn\s+\w+\s*\(|\blet\s+mut\s+", s): return "rust"
    if re.search(r"\bfunc\s+\w+\s*\(", s) and "package " in s: return "go"
    if re.search(r"\b(plugins|implementation|testImplementation)\s*[({]", s): return "gradle"
    return "text"


def _highlight_line(line: str, language: str) -> str:
    language = normalize_language(language)
    if language in {"html","xml","vue","svelte"}:
        out=[]; pos=0
        for m in re.finditer(r"<!--[\s\S]*?-->|</?[A-Za-z][^>]*>|<!DOCTYPE[^>]*>", line, re.I):
            out.append(line[pos:m.start()]); token=m.group(0)
            if token.startswith("<!--"): out.append(GRAY+token+RESET)
            else:
                token=re.sub(r"(&?[A-Za-z_:][-\w:.]*)(?=\=)", lambda x:YELLOW+x.group(1)+RESET, token)
                out.append(RED+token+RESET)
            pos=m.end()
        out.append(line[pos:]); return "".join(out)
    if language == "json":
        line=re.sub(r'("(?:[^"\\]|\\.)*")(?=\s*:)', lambda m: BLUE+m.group(1)+RESET, line)
    parts=re.split(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|#[^\n]*|//[^\n]*|/\*[\s\S]*?\*/|\b\d+(?:\.\d+)?\b)', line)
    pattern=KEYWORDS.get(language)
    out=[]
    for part in parts:
        if not part: continue
        if part.startswith(('"',"'")): out.append(GREEN+part+RESET)
        elif part.startswith(('#','//','/*')): out.append(GRAY+part+RESET)
        elif re.fullmatch(r"\d+(?:\.\d+)?", part): out.append(YELLOW+part+RESET)
        elif pattern: out.append(re.sub(pattern, lambda m: MAGENTA+m.group(0)+RESET, part))
        else: out.append(part)
    return "".join(out)


def highlight_code(code: str, language: str) -> str:
    language=normalize_language(language); code=code.replace("\r\n","\n").replace("\r","\n")
    return "\n".join(_highlight_line(line, language) for line in code.rstrip("\n").split("\n"))


def _fold_lines(lines: list[str]) -> tuple[list[tuple[int,str]], int]:
    try: limit=int(os.environ.get("CODEX_FOLD_LINES","0"))
    except ValueError: limit=0
    numbered=list(enumerate(lines,1))
    if limit<=0 or len(lines)<=limit: return numbered,0
    head=max(20,limit-20); tail=20; hidden=len(lines)-head-tail
    return numbered[:head]+[(0,f"… {hidden} baris disembunyikan; set CODEX_FOLD_LINES=0 untuk menampilkan semua …")]+numbered[-tail:],hidden


def render_code_block(language: str, code: str) -> str:
    language=detect_language(code,language)
    width=min(shutil.get_terminal_size((80,24)).columns,110)
    raw=code.replace("\r\n","\n").replace("\r","\n").rstrip("\n").split("\n") or [""]
    lines,_=_fold_lines(raw); number_width=max(2,len(str(len(raw))))
    header_text=f" {language} · {len(raw)} lines "
    header=f"{BLUE}{BOLD}┌─{header_text}{'─'*max(1,width-len(header_text)-3)}┐{RESET}"
    rendered=[header]
    for num,line in lines:
        shown=str(num).rjust(number_width) if num else "·".rjust(number_width)
        rendered.append(f"{BLUE}│{RESET} {DIM}{shown}{RESET} │ {highlight_code(line,language)}")
    rendered.append(f"{BLUE}└{'─'*max(1,width-1)}┘{RESET}")
    return "\n".join(rendered)


def _fenced_blocks(text: str):
    """Yield (start,end,language,code) for complete fenced blocks."""
    text=text.replace("\r\n","\n").replace("\r","\n")
    lines=text.splitlines(True); offset=0; opening=None
    for line in lines:
        stripped=line.rstrip("\n")
        m=re.match(r"^[ \t]{0,8}(`{3,}|~{3,})[ \t]*([^`\r\n]*)$", stripped)
        if opening is None:
            if m:
                opening=(offset,offset+len(line),m.group(1)[0],len(m.group(1)),m.group(2).strip())
        elif m:
            token=m.group(1)[0]; n=len(m.group(1))
            if token==opening[2] and n>=opening[3] and re.match(r"^[ \t]{0,8}"+re.escape(token)+r"{"+str(opening[3])+r",}[ \t]*$", stripped):
                start,end,_,_,hint=opening
                code_start=end; code_end=offset
                yield start,offset+len(line),hint,text[code_start:code_end]
                opening=None
        offset+=len(line)


def render_markdown(text: str) -> str:
    if not text:return ""
    text=text.replace("\r\n","\n").replace("\r","\n")
    out=[]; pos=0; found=False
    for start,end,hint,code in _fenced_blocks(text):
        found=True; before=text[pos:start].strip("\n")
        if before: out.append(before)
        out.append(render_code_block(hint,code)); pos=end
    tail=text[pos:].strip("\n")
    if tail:
        # Preserve an unclosed fence as a code block instead of leaking raw source.
        m=re.search(r"(?m)^[ \t]{0,8}(`{3,}|~{3,})[ \t]*([^`\r\n]*)\n",tail)
        if m:
            before=tail[:m.start()].strip("\n")
            if before: out.append(before)
            out.append(render_code_block(m.group(2),tail[m.end():]))
        else: out.append(tail)
    return "\n\n".join(out)


def extract_code_blocks(text: str) -> list[dict[str,str]]:
    text=(text or "").replace("\r\n","\n").replace("\r","\n"); blocks=[]
    for i,(_,_,hint,code) in enumerate(_fenced_blocks(text),1):
        blocks.append({"index":str(i),"language":detect_language(code,hint),"code":code})
    if not blocks:
        m=re.search(r"(?m)^[ \t]{0,8}(`{3,}|~{3,})[ \t]*([^`\r\n]*)\n",text)
        if m: blocks.append({"index":"1","language":detect_language(text[m.end():],m.group(2)),"code":text[m.end():]})
    return blocks


@dataclass
class LiveMarkdownRenderer:
    """Streaming-safe response collector. Fenced code is never printed raw."""
    text: str = ""
    last_flush: float = 0.0
    pending_output: str = ""

    def _emit(self, value: str, force: bool = False) -> None:
        if not value: return
        import sys, time
        self.pending_output += value
        now=time.monotonic()
        if force or len(self.pending_output) >= 384 or now-self.last_flush >= 0.04:
            sys.stdout.write(self.pending_output); sys.stdout.flush()
            self.pending_output=""; self.last_flush=now

    def feed(self, chunk: str) -> None:
        if chunk:
            self.text += chunk.replace("\r\n","\n").replace("\r","\n")

    def finish(self, final_text: str | None = None) -> None:
        if final_text is not None:
            self.text=final_text.replace("\r\n","\n").replace("\r","\n")
        self._emit(render_markdown(self.text)+"\n", force=True)
