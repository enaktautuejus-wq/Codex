from __future__ import annotations
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from .api import post_json, stream_json, extract_text, APIError
from .config import Config
from .tools import ToolRegistry

SYSTEM = """You are Codex, a practical terminal coding and project agent running inside Termux.

MISSION
- Make concrete progress toward the user's current request using the available workspace and tools.
- Treat the user's request as the primary task objective. Preserve the requested meaning instead of silently substituting a different task.
- Follow clear, feasible user instructions directly. Do not reject a request merely because it is unusual, terse, technical, ambitious, or unfamiliar.
- Work within the capabilities of this application, the operating system, and the remote API/model's applicable safety and provider requirements.

INSTRUCTION FOLLOWING
1. Parse the user's request carefully before acting.
2. Identify the actual requested outcome, relevant constraints, and expected deliverable.
3. If the request is sufficiently clear, act instead of asking unnecessary questions.
4. If required information is genuinely missing, ask only for the minimum information needed.
5. Do not invent requirements, goals, files, APIs, credentials, or acceptance criteria.
6. Do not silently change the user's requested scope.
7. Prefer the user's latest instruction when it supersedes an earlier instruction, while retaining still-relevant constraints.
8. If a requested step is impossible because of permissions, unavailable tools, provider behavior, or another real limitation, say exactly what is blocked and why.
9. Do not add an application-level refusal merely because a request is uncommon. Let the actual model/provider response determine remote-model restrictions.
10. Never claim that this system prompt can override a remote model or provider policy.

AUTONOMOUS CODING WORKFLOW
11. For non-trivial tasks, internally plan the smallest useful sequence of actions before executing them.
12. Inspect the project before changing it when existing context matters.
13. Discover relevant files with list/glob/grep/read rather than guessing paths.
14. Prefer focused edits over unnecessary rewrites.
15. Use the narrowest suitable tool for each operation.
16. Chain tools when that is the fastest reliable way to finish the task.
17. After meaningful code changes, run relevant tests, syntax checks, builds, linters, or other verification commands when available.
18. If verification fails, inspect the actual error, make a targeted correction, and verify again when safe and practical.
19. Continue through recoverable technical errors instead of stopping after the first failed command.
20. Stop and report a real blocker when further progress would require missing information, unavailable permissions, or an unavailable capability.
21. For larger work, maintain a todo list when it materially improves reliability.
22. Delegate focused subtasks with the task tool when doing so improves correctness or reduces context complexity.

WORKSPACE
23. The active workspace is the project directory selected during setup or later with /cd.
24. Treat that directory as the default root for file operations.
25. Keep file operations inside the active workspace unless the user explicitly specifies another path and the tool permits it.
26. Respect the workspace path supplied by the user; do not silently switch back to the Codex installation directory.
27. Inspect existing project conventions and configuration before changing important files.

TOOLS
28. Use tools whenever they materially help complete the task.
29. Use read for inspection, write for new/complete content, edit for exact replacements, patch for unified diffs, grep/glob/list for discovery, bash for terminal work, webfetch/websearch for external information, todo for task tracking, task/background for delegation, lsp for language-server analysis, project_scan for project intelligence, memory for persistent context, git for repository inspection, checkpoint for rollback points, and doctor for environment diagnosis.
30. Check arguments carefully before every tool call.
31. Use actual tool output as the source of truth for what happened.
32. Never fabricate command output, test results, file contents, paths, URLs, downloads, API responses, or deployment status.
33. If a tool returns an error, inspect it and either recover safely or report the blocker.
34. Do not repeat a failed operation indefinitely. Change the approach when repeated attempts produce the same failure.
35. Potentially destructive shell operations are protected by the application's explicit confirmation mechanism. Do not bypass that mechanism.

VERIFICATION AND REPORTING
36. After an action, report the concrete result rather than merely saying it should work.
37. When tests were run, report the actual test outcome.
38. When a command failed, report the actual failure instead of hiding it.
39. Distinguish local Codex actions from responses generated by the remote API model.
40. If the remote model refuses a request, do not pretend the CLI succeeded. State that the remote model/provider returned the refusal when that is the actual result.
41. Do not expose API keys or other secrets in responses, generated files, logs, or tool output unnecessarily.

TOOL-CALL BEHAVIOR
42. Prefer native API tool calling when the provider supports it.
43. If native tool calling is unavailable, use the application's strict JSON tool-call fallback.
44. In native mode, call only tools exposed in the tool definitions and provide valid arguments.
45. In fallback mode, when a tool is needed, return exactly one JSON object: {"tool":"NAME","args":{...}} with no surrounding prose.
46. After receiving a tool result, continue the task using the actual result.
47. Do not call a tool merely to appear busy; every tool call should advance the task.
48. Keep the user-facing final response focused on the result, relevant changes, and verification.

REMOTE MODEL / PROVIDER BOUNDARY
49. This agent can improve instruction-following, planning, tool use, retries, verification, and project awareness, but it cannot truthfully disable policies imposed by a remote model or API provider.
50. Do not attempt to bypass authentication, safety controls, or provider restrictions by disguising or hiding the user's intent.
51. Within those boundaries, be proactive, practical, and execution-oriented.

The goal is reliable execution: understand the user's actual request, use the available tools, verify the result, recover from ordinary technical failures, and report what really happened. When beginning work in a non-empty workspace, use project_scan first unless the current project context is already sufficient. Use memory to preserve important decisions and prior work. Use git/checkpoint tools before risky multi-file changes when practical. Prefer concise responses and tool calls so latency stays low.
"""

class Agent:
    def __init__(self, config: Config, registry: ToolRegistry):
        self.config = config
        self.registry = registry
        if hasattr(self.registry, "project"):
            self.project_context = self.registry.project.compact_context()
        else:
            from .project import ProjectIndex
            self.project_context = ProjectIndex(config.workspace).compact_context()
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM + "\n\nACTIVE PROJECT CONTEXT:\n" + self.project_context}]
        self.max_steps = 40
        self.native_tools = True
        self.stream_callback = None

    def _model_call(self) -> tuple[str, dict[str, Any], bool]:
        payload = {
            "model": self.config.model,
            "messages": self.messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        native = self.native_tools
        if native:
            payload["tools"] = self._native_tool_specs()
            payload["tool_choice"] = "auto"
        try:
            response = self._call_with_retry(payload)
            return extract_text(response), response, native
        except APIError as exc:
            # Some OpenAI-compatible gateways reject `tools`. Fall back once to
            # the application's JSON protocol instead of making the whole agent unusable.
            if native and self._looks_like_tool_schema_rejection(str(exc)):
                self.native_tools = False
                fallback_payload = {
                    "model": self.config.model,
                    "messages": self.messages + [{
                        "role": "system",
                        "content": "Native tool calling is unavailable. Use the strict JSON tool-call protocol from your instructions when a tool is required.",
                    }],
                    "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
                }
                response = self._call_with_retry(fallback_payload)
                return extract_text(response), response, False
            raise

    def _call_with_retry(self, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                if self.config.stream:
                    return stream_json(self.config.endpoint, self.config.api_key, payload, timeout=120, on_token=self.stream_callback)
                return post_json(self.config.endpoint, self.config.api_key, payload)
            except APIError as exc:
                last = exc
                message = str(exc).lower()
                retryable = any(x in message for x in (
                    "timeout", "timed out", "tempor", "connection", "502", "503", "504", "429"
                ))
                if "stream" in message and any(x in message for x in ("unsupported", "not supported", "unknown field", "invalid parameter")) and self.config.stream:
                    self.config.stream = False
                    continue
                if attempt + 1 >= attempts or not retryable:
                    raise
                time.sleep(0.35 * (attempt + 1))
        raise last or APIError("API request failed")

    @staticmethod
    def _looks_like_tool_schema_rejection(message: str) -> bool:
        m = message.lower()
        return any(term in m for term in (
            "tools is not supported", "tool_choice", "unknown field", "unrecognized field",
            "extra inputs are not permitted", "invalid parameter: tools", "unsupported parameter"
        ))

    def _native_tool_specs(self) -> list[dict[str, Any]]:
        specs = []
        for spec in self.registry.specs():
            parameters = self._tool_parameters_schema(spec.get("parameters", {}))
            specs.append({
                "type": "function",
                "function": {
                    "name": spec["name"],
                    "description": spec["description"],
                    "parameters": parameters,
                },
            })
        return specs

    @staticmethod
    def _tool_parameters_schema(parameters: dict[str, Any]) -> dict[str, Any]:
        props: dict[str, Any] = {}
        required: list[str] = []
        for name, kind in parameters.items():
            if kind == "string":
                props[name] = {"type": "string"}
                required.append(name)
            elif kind == "integer":
                props[name] = {"type": "integer"}
            elif kind == "array":
                props[name] = {"type": "array", "items": {"type": "string"}}
            elif kind == "integer|null":
                props[name] = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
            elif kind == "string|null":
                props[name] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
            elif "|" in kind:
                options = kind.split("|")
                props[name] = {"type": "string", "enum": options}
                required.append(name)
            else:
                props[name] = {"type": "string"}
        return {"type": "object", "properties": props, "required": required, "additionalProperties": False}

    @staticmethod
    def _native_calls(response: dict[str, Any]) -> list[dict[str, Any]]:
        choices = response.get("choices") or []
        if not choices:
            return []
        message = choices[0].get("message") or {}
        calls = message.get("tool_calls") or []
        return [c for c in calls if isinstance(c, dict) and isinstance(c.get("function"), dict)]

    @staticmethod
    def _parse_tool_call(text: str) -> dict[str, Any] | None:
        stripped = text.strip()
        if stripped.startswith("```") and stripped.endswith("```"):
            parts = stripped.split("\n", 1)
            stripped = parts[1] if len(parts) == 2 else stripped
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

    def _execute_tool(self, name: str, args: dict[str, Any]) -> Any:
        if name == "bash" and self._looks_destructive(args.get("command", "")):
            return {"error":"Perintah shell berpotensi destruktif. Konfirmasi eksplisit diperlukan.","confirmation":f"CONFIRM {args.get('command','')}"}
        if name == "checkpoint" and args.get("action") == "restore":
            return {"error":"Pemulihan checkpoint mengganti file proyek. Konfirmasi eksplisit diperlukan.","confirmation":f"CONFIRM CHECKPOINT {args.get('name','')}"}
        try:
            return self.registry.call(name, args, self._subagent)
        except Exception as exc:
            return {"error": str(exc)}

    def run_once(self) -> str:
        for _ in range(self.max_steps):
            response_text, response_json, native = self._model_call()
            calls = self._native_calls(response_json) if native else []
            if calls:
                choices = response_json.get("choices") or []
                assistant_message = (choices[0].get("message") or {}) if choices else {}
                self.messages.append({
                    "role": "assistant",
                    "content": assistant_message.get("content"),
                    "tool_calls": calls,
                })
                prepared=[]
                for call in calls:
                    fn = call.get("function") or {}
                    name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    try: args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                    except json.JSONDecodeError: args = {}
                    prepared.append((call, name, args))
                results=[]
                with ThreadPoolExecutor(max_workers=min(6, len(prepared) or 1)) as pool:
                    futures={pool.submit(self._execute_tool, name, args):(call,name,args) for call,name,args in prepared}
                    for fut in as_completed(futures):
                        call,name,args=futures[fut]
                        try: result=fut.result()
                        except Exception as exc: result={"error":str(exc)}
                        results.append((call,result))
                order={call.get("id",""):i for i,(call,_,_) in enumerate(prepared)}
                for call,result in sorted(results,key=lambda x: order.get(x[0].get("id",""),0)):
                    self.messages.append({"role":"tool","tool_call_id":call.get("id",""),"content":json.dumps(result,ensure_ascii=False,default=str)})
                continue

            fallback_call = self._parse_tool_call(response_text) if not native else None
            if not fallback_call:
                self.messages.append({"role": "assistant", "content": response_text})
                return response_text

            name = fallback_call["tool"]
            args = fallback_call.get("args") or {}
            result = self._execute_tool(name, args)
            self.messages.append({"role": "assistant", "content": response_text})
            self.messages.append({
                "role": "user",
                "content": "TOOL_RESULT " + json.dumps({"tool": name, "result": result}, ensure_ascii=False, default=str),
            })
        return "Batas langkah agent tercapai; sesi dihentikan setelah 50 langkah."

    @staticmethod
    def _looks_destructive(command: str) -> bool:
        patterns = [
            r"\brm\s+-rf\b", r"\bmkfs\b", r"\bdd\s+if=",
            r"\bdrop\s+(database|table)\b", r"\bgit\s+reset\s+--hard\b",
            r"\bgit\s+clean\s+-fd\b", r"\bshutdown\b", r"\breboot\b",
        ]
        return any(re.search(p, command, re.I) for p in patterns)

    def run(self, user_text: str) -> str:
        if user_text.startswith("CONFIRM CHECKPOINT "):
            name=user_text[len("CONFIRM CHECKPOINT "):].strip()
            return json.dumps(self.registry.call("checkpoint", {"action":"restore","name":name}), ensure_ascii=False)
        if user_text.startswith("CONFIRM "):
            command = user_text[len("CONFIRM "):].strip()
            result = self.registry.call("bash", {"command": command, "cwd": "."})
            return json.dumps(result, ensure_ascii=False)
        memory_context = self.registry.memory.context(user_text, 5)
        if memory_context:
            self.messages.append({"role": "system", "content": "RELEVANT MEMORY:\n" + memory_context})
        self.messages.append({"role": "user", "content": user_text})
        self.registry.memory.add("user", user_text)
        answer = self.run_once()
        self.registry.memory.add("assistant", answer)
        return answer
