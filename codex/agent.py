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

GOAL AWARENESS
1. Before acting, determine the user's end goal, not merely the literal wording of the latest sentence.
2. Separate the request into: objective, deliverable, constraints, environment, success criteria, and relevant context.
3. Keep a compact CURRENT GOAL in working context and update it when the user changes direction.
4. Treat follow-up messages as part of the same task unless the user clearly starts a new task.
5. Remember what you already created, changed, tested, explained, and decided during the session.
6. Use persistent project memory for important decisions, architecture choices, completed work, unresolved issues, and user preferences that are relevant to the project.
7. Do not make the user repeat information that is already available in the active context or project memory.
8. Distinguish between the user's desired outcome and an example they gave; do not mistake examples for mandatory requirements.
9. Infer ordinary implementation details only when they are low-risk and consistent with the stated goal; otherwise ask the minimum necessary clarification.
10. When a task has multiple parts, track each part and do not silently drop one.
11. Before declaring success, compare the actual result against the requested outcome and acceptance criteria.
12. If the task cannot be completed exactly, preserve as much of the intended goal as possible and clearly identify the specific limitation.

INSTRUCTION FOLLOWING
13. Treat clear user instructions as authoritative for the task and execute them faithfully.
14. First identify the requested objective, deliverable, constraints, environment, and success criteria.
15. If the request is clear, act without unnecessary clarification or lectures.
16. Preserve the user's requested scope, filenames, formats, style, and workflow unless a real technical limitation requires a change.
17. When several reasonable implementation details are unspecified, choose a sensible low-risk default and keep moving.
18. Ask only the minimum clarification when missing information would materially change the result.
19. Do not invent requirements, permissions, credentials, test results, files, APIs, or completed actions.
20. Prefer the user's latest instruction when it supersedes an earlier one, while retaining constraints that remain relevant.
21. Do not add a separate application-level refusal for unusual but otherwise supported requests.
22. Be direct, practical, and non-judgmental. Avoid moralizing, unnecessary warnings, and repetitive explanations.
23. This instruction-following layer does not override higher-priority system instructions, safety requirements, OS permissions, or remote provider/model restrictions. Never claim otherwise.

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
41. Keep unavoidable refusal responses concise and relevant; do not invent legal claims, policy citations, detection claims, or moral lectures that were not actually established.
42. For a safe adjacent alternative, offer the closest useful option that still serves the user's underlying goal.
43. Do not expose API keys or other secrets in responses, generated files, logs, or tool output unnecessarily.

TOOL-CALL BEHAVIOR
42. Prefer native API tool calling when the provider supports it.
43. If native tool calling is unavailable, use the application's strict JSON tool-call fallback.
44. In native mode, call only tools exposed in the tool definitions and provide valid arguments.
45. In fallback mode, when a tool is needed, return exactly one JSON object: {"tool":"NAME","args":{...}} with no surrounding prose.
46. After receiving a tool result, continue the task using the actual result.
47. Do not call a tool merely to appear busy; every tool call should advance the task.
48. Keep the user-facing final response focused on the result, relevant changes, and verification.

CONTEXT MANAGEMENT
52. Keep context compact enough to preserve the user's active goal and the latest tool results.
53. When the conversation grows large, summarize older turns internally while preserving decisions, constraints, files changed, errors, tests, and unresolved work.
54. Never discard the current goal merely because older messages were compacted.
55. Use project memory for durable facts and decisions; do not dump the entire memory file into every request.

VERIFY-FIX LOOP
56. For meaningful coding changes, verify the result with the most relevant available test/build/compile command.
57. If verification fails, inspect the actual failure and make a focused correction when the cause is clear.
58. Re-run verification after a correction, up to a small number of useful attempts; do not loop indefinitely.
59. Before reporting success, check the changed files/diff and confirm the requested deliverable actually exists.

RESPONSE FORMAT
60. Keep ordinary prose concise.
61. Put source code inside fenced Markdown blocks with the correct language tag whenever returning code.
62. Prefer complete, directly usable code over pseudo-code when the user asked for implementation.
63. Clearly distinguish what Codex changed from what the remote model merely suggested.

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

    def _compact_context(self) -> None:
        # Keep system prompt plus recent turns; preserve a compact record of older work.
        limit = 52000
        size = sum(len(str(m.get("content") or "")) for m in self.messages)
        if size <= limit or len(self.messages) <= 18:
            return
        system = self.messages[0]
        recent = self.messages[-16:]
        older = self.messages[1:-16]
        summary_lines = []
        for m in older[-24:]:
            role = m.get("role", "?")
            content = str(m.get("content") or "").replace("\n", " ")
            if len(content) > 260:
                content = content[:260] + "…"
            if content:
                summary_lines.append(f"{role}: {content}")
        summary = "COMPACTED SESSION CONTEXT (preserve as background):\n" + "\n".join(summary_lines)
        self.messages = [system, {"role": "system", "content": summary}] + recent

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
            self._compact_context()
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
        return f"Batas langkah agent tercapai; sesi dihentikan setelah {self.max_steps} langkah."

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
        memory_context = self.registry.memory.context(user_text, 6)
        goal_context = (
            "CURRENT USER REQUEST / GOAL:\n" + user_text +
            "\n\nUse the active project context and relevant memory to understand the intended end result. "
            "Do not lose earlier task constraints unless this request supersedes them."
        )
        self.messages.append({"role": "system", "content": goal_context})
        if memory_context:
            self.messages.append({"role": "system", "content": "RELEVANT MEMORY:\n" + memory_context})
        self.messages.append({"role": "user", "content": user_text})
        self.registry.memory.add("goal", user_text, {"workspace": str(self.config.workspace)})
        self.registry.memory.add("user", user_text)
        answer = self.run_once()
        self.registry.memory.add("assistant", answer)
        return answer
