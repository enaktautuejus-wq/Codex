from __future__ import annotations
import os
import shutil
import sys
from getpass import getpass
from .config import Config, normalize_base_url
from .tools import Workspace

RED = "\033[91m"
CYAN = "\033[96m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

def clear():
    print(CLEAR, end="")

def mask_key(key: str) -> str:
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

def setup() -> Config:
    clear()
    print("Codex setup\n")
    while True:
        try:
            base = normalize_base_url(input("Base url: "))
            break
        except ValueError as exc:
            print(f"{RED}Error:{RESET} {exc}")
    key = getpass("api key: ").strip()
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

def choose_workspace() -> str:
    """Prompt for the folder Codex should operate in, then return an absolute path."""
    while True:
        raw = input("Path folder: ").strip()
        if not raw:
            print(f"{RED}Error:{RESET} Path folder wajib diisi.")
            continue
        candidate = os.path.abspath(os.path.expanduser(raw))
        if not os.path.isdir(candidate):
            print(f"{RED}Error:{RESET} Folder tidak ditemukan: {candidate}")
            continue
        try:
            os.chdir(candidate)
        except OSError as exc:
            print(f"{RED}Error:{RESET} Tidak bisa masuk ke folder: {exc}")
            continue
        print(f"Path folder: {candidate}")
        print(f"{CYAN}Workspace aktif. Membuka Codex...{RESET}\n")
        return candidate

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

def _change_workspace(agent, config, registry, raw_path: str):
    raw_path = raw_path.strip()
    if not raw_path:
        return "Workspace saat ini: " + str(registry.ws.root)
    candidate = os.path.abspath(os.path.expanduser(raw_path))
    if not os.path.isdir(candidate):
        return f"Workspace tidak ditemukan atau bukan direktori: {candidate}"
    os.chdir(candidate)
    registry.ws = Workspace(candidate)
    config.workspace = candidate
    agent.messages.append({
        "role": "system",
        "content": f"Workspace aktif sekarang: {candidate}. Gunakan workspace ini untuk operasi file dan shell.",
    })
    return f"Workspace aktif: {candidate}"

def run_ui(agent, config, registry):
    clear()
    banner(config)
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
            agent.messages = [{"role":"system","content":agent.messages[0]["content"]}]
            clear(); banner(config); continue
        if text == "/pwd":
            print(f"Workspace: {registry.ws.root}\n")
            continue
        if text.startswith("/cd"):
            target = text[3:].strip()
            print(_change_workspace(agent, config, registry, target) + "\n")
            continue
        if text == "/tools":
            for spec in registry.specs():
                print(f"- {spec['name']}: {spec['description']}")
            print()
            continue
        if text == "/todo":
            print(registry.todo.run("read")); print(); continue
        try:
            answer = agent.run(text)
            print(f"{CYAN}root@ai-codex:~#{RESET}")
            print(answer)
            print()
        except Exception as exc:
            print(f"{RED}API/tool error:{RESET} {exc}\n")
