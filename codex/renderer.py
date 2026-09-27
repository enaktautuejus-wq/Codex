from __future__ import annotations
import re
import shutil

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
GRAY = "\033[90m"

FENCE_RE = re.compile(r"(?ms)^```([^\n`]*)\n(.*?)^```[ \t]*$")

LANG_ALIASES = {
    "py": "python", "python3": "python", "js": "javascript", "jsx": "javascript",
    "ts": "typescript", "tsx": "typescript", "sh": "bash", "shell": "bash", "zsh": "bash",
    "yml": "yaml", "md": "markdown", "text": "text", "plaintext": "text",
}

KEYWORDS = {
    "python": r"\b(def|class|import|from|as|if|elif|else|for|while|in|try|except|finally|with|return|yield|lambda|True|False|None|and|or|not|is|async|await|pass|raise|assert)\b",
    "javascript": r"\b(function|const|let|var|if|else|for|while|return|class|new|import|from|export|async|await|try|catch|throw|true|false|null|undefined)\b",
    "typescript": r"\b(function|const|let|var|if|else|for|while|return|class|new|import|from|export|async|await|try|catch|throw|true|false|null|undefined|interface|type|public|private)\b",
    "bash": r"\b(if|then|else|fi|for|while|in|do|done|case|esac|function|export|local|source|return)\b",
    "json": r'"(?:[^"\\]|\\.)*"(?=\s*:)',
    "yaml": r"^\s*[A-Za-z_][\w.-]*(?=:\s)",
}


def normalize_language(raw: str) -> str:
    lang = raw.strip().lower().split()[0] if raw.strip() else "text"
    return LANG_ALIASES.get(lang, lang)


def _highlight_line(line: str, language: str) -> str:
    # Keep highlighting deliberately lightweight and dependency-free for Termux.
    pattern = KEYWORDS.get(language)
    if not pattern:
        return line
    parts = re.split(r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'|#[^\n]*|//[^\n]*|\b\d+(?:\.\d+)?\b)", line)
    out = []
    for part in parts:
        if not part:
            continue
        if part.startswith(("\"", "'")):
            out.append(GREEN + part + RESET)
        elif part.startswith("#") or part.startswith("//"):
            out.append(GRAY + part + RESET)
        elif re.fullmatch(r"\d+(?:\.\d+)?", part):
            out.append(YELLOW + part + RESET)
        else:
            out.append(re.sub(pattern, lambda m: MAGENTA + m.group(0) + RESET, part))
    return "".join(out)


def highlight_code(code: str, language: str) -> str:
    language = normalize_language(language)
    return "\n".join(_highlight_line(line, language) for line in code.rstrip("\n").splitlines())


def render_code_block(language: str, code: str) -> str:
    language = normalize_language(language)
    width = min(shutil.get_terminal_size((80, 24)).columns, 110)
    header = f"{BLUE}{BOLD}┌─ {language} ─{'─' * max(1, width - len(language) - 5)}┐{RESET}"
    body = highlight_code(code, language)
    lines = body.splitlines() or [""]
    rendered = [header]
    for line in lines:
        # ANSI escape sequences do not count toward the visual width; keep a simple
        # left border rather than padding highlighted text to avoid broken wrapping.
        rendered.append(f"{BLUE}│{RESET} {line}")
    rendered.append(f"{BLUE}└{'─' * max(1, width - 1)}┘{RESET}")
    return "\n".join(rendered)


def render_markdown(text: str) -> str:
    """Separate fenced code from normal text and render code with language-aware ANSI colors."""
    output = []
    pos = 0
    for match in FENCE_RE.finditer(text):
        before = text[pos:match.start()].rstrip("\n")
        if before:
            output.append(before)
        output.append(render_code_block(match.group(1), match.group(2)))
        pos = match.end()
    tail = text[pos:].strip("\n")
    if tail:
        output.append(tail)
    return "\n\n".join(output)
