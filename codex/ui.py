from __future__ import annotations
import os
import shutil
import sys
import termios
import tty
from .config import Config, normalize_base_url

RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"
ALT_SCREEN_ON = "\033[?1049h\033[?25l"
ALT_SCREEN_OFF = "\033[?25h\033[?1049l"

def clear():
    print(CLEAR, end="")

def enter_fullscreen():
    sys.stdout.write(ALT_SCREEN_ON)
    sys.stdout.flush()

def leave_fullscreen():
    sys.stdout.write(ALT_SCREEN_OFF)
    sys.stdout.flush()

def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

def _read_masked(prompt: str = "api key: ") -> str:
    """Read a secret in a Termux-friendly way and show * per character.

    Python's getpass hides all terminal echo. That is awkward on Android/Termux
    because the user gets no visual feedback when typing or pasting. This
    reader keeps canonical terminal input disabled only while reading, echoes
    a harmless mask character, and restores the terminal state on every exit.
    """
    if not sys.stdin.isatty():
        # Useful for pipes/tests/non-interactive environments.
        return input(prompt)

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    chars: list[str] = []
    sys.stdout.write(prompt)
    sys.stdout.flush()
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                sys.stdout.write("\n")
                sys.stdout.flush()
                return "".join(chars)
            if ch == "\x03":
                raise KeyboardInterrupt
            if ch == "\x04":
                raise EOFError
            if ch in ("\x7f", "\b"):
                if chars:
                    chars.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue
            # Ignore other terminal control characters, but keep normal API-key
            # characters including punctuation and symbols.
            if ch.isprintable():
                chars.append(ch)
                sys.stdout.write("*")
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)

def setup() -> Config:
    clear()
    print("Codex setup\n")
    while True:
        try:
            base = normalize_base_url(input("Base url: "))
            break
        except ValueError as exc:
            print(f"{RED}Error:{RESET} {exc}")
    key = _read_masked("api key (ketik/tempel, tampil sebagai *): ").strip()
    model = input("id model: ").strip()
    if not key or not model:
        raise ValueError("API key dan model wajib diisi.")
    workspace = os.path.abspath(os.environ.get("CODEX_WORKSPACE", os.getcwd()))
    return Config(base, key, model, workspace)

def verify(config: Config, api_call):
    clear()
    print("Verifikasi api: loading...", flush=True)
    try:
        api_call()
    except Exception as exc:
        print(f"{RED}Verifikasi gagal:{RESET} {exc}")
        raise SystemExit(1)
    print(f"{CYAN}Verifikasi api: berhasil.{RESET}")

def banner(config: Config):
    print(RED + r"""
 ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝
██║     ██║   ██║██║  ██║█████╗   ╚███╔╝
██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗
╚██████╗╚██████╔╝██████╔╝███████╗██╔╝ ██╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
""" + RESET)
    print(f"api key: {mask_key(config.api_key)}")
    print(f"base url: {config.base_url}")
    print(f"model: {config.model}")
    print("\n" + "─" * min(shutil.get_terminal_size((80,24)).columns, 100) + "\n")

def run_ui(agent, config, registry):
    enter_fullscreen()
    clear()
    banner(config)
    try:
        while True:
            try:
                text = input(f"{RED}root@codex:~#{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not text:
                continue
            if text in {"/exit", "/quit"}:
                break
            if text == "/clear":
                agent.messages = [{"role": "system", "content": agent.messages[0]["content"]}]
                clear()
                banner(config)
                continue
            if text == "/tools":
                for spec in registry.specs():
                    print(f"- {spec['name']}: {spec['description']}")
                print()
                continue
            if text == "/todo":
                print(registry.todo.run("read"))
                print()
                continue
            try:
                answer = agent.run(text)
                print(f"{CYAN}root@ai-codex:~#{RESET}")
                print(answer)
                print()
            except Exception as exc:
                print(f"{RED}API/tool error:{RESET} {exc}\n")
    finally:
        leave_fullscreen()
