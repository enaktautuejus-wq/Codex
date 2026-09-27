from __future__ import annotations
import json
import re
from typing import Any
from .api import post_json, extract_text, APIError
from .config import Config
from .tools import ToolRegistry, ToolError

SYSTEM = """You are Codex, a terminal coding/building agent.
You work inside a Termux workspace.
Use tools when they are useful. Inspect files before modifying existing files.
After modifying code, verify it with appropriate tests, type checks, linters, or
build commands when available.
Never claim a tool action succeeded unless the tool result says it succeeded.
Tool calls must be returned as strict JSON objects:
{"tool":"NAME","args":{...}}
When no tool is needed, answer normally.
"""

class Agent:
    def __init__(self, config: Config, registry: ToolRegistry):
        self.config = config
        self.registry = registry
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
        self.max_steps = 30

    def _model_call(self) -> str:
        payload = {
            "model": self.config.model,
            "messages": self.messages,
            "temperature": 0.2,
        }
        response = post_json(self.config.endpoint, self.config.api_key, payload)
        return extract_text(response)

    @staticmethod
    def _parse_tool_call(text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            stripped = stripped.split("\n", 1)[1]
            stripped = stripped.rsplit("```", 1)[0].strip()
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        if isinstance(obj, dict) and isinstance(obj.get("tool"), str):
            return obj
        return None

    def _subagent(self, prompt: str, role: str) -> str:
        child = Agent(self.config, self.registry)
        child.messages.append({
            "role": "user",
            "content": f"Role: {role}\nSubtask:\n{prompt}\nReturn only the useful result.",
        })
        return child.run_once()

    def run_once(self) -> str:
        for _ in range(self.max_steps):
            response = self._model_call()
            call = self._parse_tool_call(response)
            if not call:
                self.messages.append({"role": "assistant", "content": response})
                return response

            name = call["tool"]
            args = call.get("args") or {}

            # Irreversible shell operations get an explicit confirmation.
            if name == "bash" and self._looks_destructive(args.get("command", "")):
                return (
                    "Perintah shell yang berpotensi destruktif terdeteksi. "
                    "Jalankan ulang dengan konfirmasi eksplisit: "
                    "`CONFIRM <command>`."
                )

            try:
                result = self.registry.call(name, args, self._subagent)
            except Exception as exc:
                result = {"error": str(exc)}

            self.messages.append({"role": "assistant", "content": response})
            # Keep tool results provider-compatible: plain chat-completions
            # endpoints do not all implement the newer tool_call protocol.
            self.messages.append({
                "role": "user",
                "content": (
                    f"TOOL RESULT ({name}):\n"
                    + json.dumps(result, ensure_ascii=False, default=str)
                    + "\nContinue the task using this result."
                ),
            })

        return "Batas langkah agent tercapai; sesi dihentikan sebelum loop berlanjut."

    @staticmethod
    def _looks_destructive(command: str) -> bool:
        patterns = [
            r"\brm\s+-rf\b",
            r"\bmkfs\b",
            r"\bdd\s+if=",
            r"\bdrop\s+(database|table)\b",
            r"\bgit\s+reset\s+--hard\b",
            r"\bgit\s+clean\s+-fd\b",
            r"\bshutdown\b",
            r"\breboot\b",
        ]
        return any(re.search(p, command, re.I) for p in patterns)

    def run(self, user_text: str) -> str:
        if user_text.startswith("CONFIRM "):
            command = user_text[len("CONFIRM "):].strip()
            result = self.registry.call("bash", {"command": command, "cwd": "."})
            return json.dumps(result, ensure_ascii=False)
        self.messages.append({"role": "user", "content": user_text})
        return self.run_once()
