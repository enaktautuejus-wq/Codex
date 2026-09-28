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

AUTOMATIC TOOL EXECUTION
- Do not ask the user for permission before using an available tool when the tool operation is already required by the user request.
- Execute ordinary read, search, project inspection, file creation/editing, verification, diagnostics, and other non-destructive tools directly.
- Do not emit approval questions such as "May I run this?", "Should I execute this?", or "Do you want me to create the file?" when the requested task already clearly requires the action.
- Treat the user's explicit task request as authorization for ordinary non-destructive tool execution within the active workspace and requested paths.
- Continue from tool results instead of stopping to ask for permission.
- This instruction does not remove system instructions, provider restrictions, OS permissions, authentication requirements, or the application's existing safeguards for destructive operations.

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
39. For implementation or debugging requests, inspect relevant project files before proposing a solution; do not answer from generic knowledge when repository evidence is available.
40. Prefer action over narration: if a supported tool can directly inspect, edit, test, or verify the workspace, use it.
41. For non-trivial tasks, internally plan the smallest useful sequence of actions before executing them.
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

PROJECT KNOWLEDGE
27. The ACTIVE PROJECT CONTEXT is authoritative for the current workspace state at startup.
28. Do not claim you know a project's architecture without inspecting the supplied project context or relevant files.
29. For implementation requests, use the project context first, then read/search the exact files needed before editing.
30. Prefer concrete repository evidence over generic assumptions.
31. If the project context is incomplete, use project_scan, list, glob, grep, and read to fill the gap before making architectural changes.

TOOLS
32. Use tools whenever they materially help complete the task.
32. Use read for inspection, write for new/complete content, edit for exact replacements, patch for unified diffs, grep/glob/list for discovery, bash for terminal work, webfetch/websearch for external information, todo for task tracking, task/background for delegation, lsp for language-server analysis, project_scan for project intelligence, memory for persistent context, git for repository inspection, checkpoint for rollback points, and doctor for environment diagnosis.
33. Check arguments carefully before every tool call.
34. Use actual tool output as the source of truth for what happened.
35. Never fabricate command output, test results, file contents, paths, URLs, downloads, API responses, or deployment status.
36. If a tool returns an error, inspect it and either recover safely or report the blocker.
37. Do not repeat a failed operation indefinitely. Change the approach when repeated attempts produce the same failure.
38. Potentially destructive shell operations are protected by the application's explicit confirmation mechanism. Do not bypass that mechanism.

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

EXECUTION-FIRST CONTROLLER
- Codex is an execution agent, not a text-only chatbot.
- For ordinary supported project actions, prefer executing the requested action with tools over merely explaining how the user could do it.
- A clear actionable request is not complete merely because the model produced instructions for the user.
- If the model returns prose for an actionable workspace request without using a relevant tool, the controller may issue one concise execution reminder and give the model another chance to select tools.
- The reminder must never be used to override system instructions, safety requirements, provider restrictions, authentication, permissions, or destructive-command confirmation.
- After a successful tool call, use its actual result and continue until the requested outcome is verified or a concrete blocker remains.
- Do not fabricate tool use or pretend an action was completed.

REMOTE MODEL / PROVIDER BOUNDARY
49. This agent can improve instruction-following, planning, tool use, retries, verification, and project awareness, but it cannot truthfully disable policies imposed by a remote model or API provider.
50. Do not attempt to bypass authentication, safety controls, or provider restrictions by disguising or hiding the user's intent.
51. Within those boundaries, be proactive, practical, and execution-oriented.

TOOL OPERATING MANUAL — USE THIS IN ADDITION TO ALL INSTRUCTIONS ABOVE

A. TOOL SELECTION
- project_scan: use first when project structure or architecture is unknown.
- list/glob: discover paths; do not guess filenames.
- grep: locate symbols, strings, imports, routes, configuration, or references.
- read: inspect exact relevant file content before editing. Use line ranges for large files.
- edit: preferred for a small exact replacement.
- patch: preferred for structured multi-line changes when a unified diff is clearer.
- write: use for a new file or deliberate full replacement.
- bash: run tests, builds, formatters, package managers, git commands, and other project commands.
- verify: use after meaningful implementation changes.
- diff/git: inspect what actually changed before declaring success.
- lsp: use when a supported language server is available for symbols/diagnostics/definitions.
- memory: search durable project decisions and save important new decisions; memory lives outside the workspace.
- delete: delete an explicitly requested file or directory; use confirmed=true only when the user explicitly requested deletion, and recursive=true for non-empty directories.
- goal: keep the project's actual objective and acceptance criteria persistent.
- checkpoint: create a rollback point before broad or risky edits when practical.
- task/background: delegate focused research or analysis when it improves reliability.
- websearch/webfetch: use for current or external technical information when repository evidence is insufficient.
- doctor: diagnose environment/tool/API problems rather than guessing.

B. STANDARD CODING LOOP
1. Understand goal and acceptance criteria.
2. project_scan or inspect the relevant files.
3. Search for the exact implementation points.
4. Read the relevant files.
5. Plan the smallest coherent change.
6. Edit/write/patch.
7. Run the most relevant verification.
8. If verification fails, inspect the real error and fix it.
9. Re-run verification.
10. Inspect diff and report the concrete result.

C. TOOL ARGUMENT DISCIPLINE
- Paths are relative to the active workspace unless an explicit absolute path is required.
- Do not send placeholder arguments when the real value is known from tool output.
- Keep tool calls narrow; combine independent read-only inspections when native parallel calls are supported.
- Use actual returned output as evidence for the next action.
- Never claim a tool ran if it did not.

D. RECOVERY
- If a tool fails because of an invalid argument, correct the argument and retry once.
- If a command fails, inspect stderr/stdout before changing strategy.
- If a provider rejects native tools, use the built-in JSON tool protocol.
- If the provider rejects an optional API parameter, retry without that optional parameter.
- If context length is rejected, compact older conversational turns while preserving the system prompt, current goal, project facts, decisions, errors, and recent tool results; do not impose a fixed model context size.

E. KNOWLEDGE
- Repository evidence beats assumptions.
- Current tool output beats stale memory.
- Persistent memory is for durable decisions, not a dump of every chat token.
- The provider/model controls its supported context and output limits; never pretend Codex knows a limit it was not given.

F. RESPONSE QUALITY
- For code, return complete usable code when the user asks for code.
- Put code in fenced Markdown blocks with a language tag whenever practical.
- Keep explanations proportional to the request.
- Do not expose internal chain-of-thought; provide concise conclusions and evidence.

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
        provider_note = (
            f"\n\nRUNTIME MODEL CONTEXT\nModel: {config.model}\n"
            "Context/output limits: controlled by the selected provider/model; Codex does not impose a fixed model limit. "
            "Do not invent a context-window number. If the provider reports a context-length error, compact older turns and retry while preserving the current goal and essential project facts."
        )
        self.messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM + provider_note + "\n\nACTIVE PROJECT CONTEXT:\n" + self.project_context}]
        self.max_steps = 40
        self.native_tools = True
        self.stream_callback = None
        self.execution_reminders = 0

    def _compact_context(self, force: bool = False) -> None:
        """Compact only when necessary; do not guess a provider's context window."""
        if not force:
            return
        if len(self.messages) <= 10:
            return
        system = self.messages[0]
        recent = self.messages[-12:]
        older = self.messages[1:-12]
        summary_lines = []
        for m in older[-32:]:
            role = m.get("role", "?")
            content = str(m.get("content") or "").replace("\n", " ")
            if len(content) > 420:
                content = content[:420] + "…"
            if content:
                summary_lines.append(f"{role}: {content}")
        summary = "COMPACTED SESSION CONTEXT (preserve as background):\n" + "\n".join(summary_lines)
        self.messages = [system, {"role": "system", "content": summary}] + recent

    def _model_call(self) -> tuple[str, dict[str, Any], bool]:
        payload = {
            "model": self.config.model,
            "messages": self.messages,
            "temperature": self.config.temperature,
        }
        if self.config.max_tokens is not None:
            payload["max_tokens"] = self.config.max_tokens
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
                }
                if self.config.max_tokens is not None:
                    fallback_payload["max_tokens"] = self.config.max_tokens
                response = self._call_with_retry(fallback_payload)
                return extract_text(response), response, False
            raise

    def _call_with_retry(self, payload: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                callback = self.stream_callback if self.native_tools else None
                if self.config.stream:
                    return stream_json(self.config.endpoint, self.config.api_key, payload, timeout=120, on_token=callback)
                return post_json(self.config.endpoint, self.config.api_key, payload)
            except APIError as exc:
                last = exc
                message = str(exc).lower()
                if any(x in message for x in (
                    "context length", "context_length", "maximum context", "too many tokens",
                    "prompt is too long", "input is too long", "token limit", "max context"
                )):
                    self._compact_context(force=True)
                    if attempt + 1 < attempts:
                        continue
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
            elif kind == "boolean":
                props[name] = {"type": "boolean"}
                required.append(name)
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

    @staticmethod
    def _is_actionable_request(text: str) -> bool:
        """Detect ordinary project-action requests; do not treat general questions as tool mandates."""
        t = text.lower()
        action_terms = (
            "buat ", "bikin ", "tambahkan", "tambah ", "hapus ", "ubah ", "edit ",
            "perbaiki", "fix ", "betulkan", "implement", "implementasikan", "jalankan",
            "run ", "test ", "uji ", "build", "compile", "install", "buatkan", "tulis ",
            "refactor", "rename", "pindahkan", "cek file", "baca file", "lihat file",
            "scan project", "analisis project", "commit", "format", "lint", "debug",
            "update file", "modifikasi", "generate file", "create file", "delete file",
        )
        object_terms = (
            ".py", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".yaml",
            ".yml", ".java", ".kt", ".gradle", ".go", ".rs", ".cpp", ".c", ".cs",
            "project", "repo", "repository", "folder", "workspace", "kode", "code",
            "aplikasi", "app", "package", "dependency",
        )
        return any(x in t for x in action_terms) and any(x in t for x in object_terms)

    def _execution_reminder(self, user_request: str) -> None:
        self.messages.append({
            "role": "system",
            "content": (
                "EXECUTION REMINDER: The current user request is an actionable project task. "
                "If the requested operation is supported by an available tool, execute it now rather than "
                "returning instructions for the user to perform manually. Inspect first when needed, then use "
                "the narrowest appropriate tool, read its result, continue, and verify. Do not fabricate results. "
                "This reminder does not override higher-priority system instructions, safety requirements, "
                "provider restrictions, OS permissions, or destructive-operation confirmation."
            ),
        })

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
                    serialized = json.dumps(result, ensure_ascii=False, default=str)
                    self.messages.append({"role":"tool","tool_call_id":call.get("id",""),"content":serialized})
                    compact = serialized if len(serialized) <= 1200 else serialized[:1200] + "…"
                    self.registry.memory.add("tool", compact, {"tool": call.get("function", {}).get("name", ""), "workspace": str(self.config.workspace)})
                continue

            fallback_call = self._parse_tool_call(response_text) if not native else None
            if not fallback_call:
                # For ordinary actionable project requests, give the model one concise
                # execution-oriented retry before accepting a text-only response.
                current_request = ""
                for msg in reversed(self.messages):
                    if msg.get("role") == "user" and isinstance(msg.get("content"), str):
                        current_request = msg["content"]
                        break
                if self.execution_reminders < 3 and self._is_actionable_request(current_request):
                    self.messages.append({"role": "assistant", "content": response_text})
                    self.execution_reminders += 1
                    self._execution_reminder(current_request)
                    continue
                self.messages.append({"role": "assistant", "content": response_text})
                return response_text

            name = fallback_call["tool"]
            args = fallback_call.get("args") or {}
            result = self._execute_tool(name, args)
            self.messages.append({"role": "assistant", "content": response_text})
            tool_serialized = json.dumps({"tool": name, "result": result}, ensure_ascii=False, default=str)
            self.messages.append({
                "role": "user",
                "content": "TOOL_RESULT " + tool_serialized,
            })
            compact = tool_serialized if len(tool_serialized) <= 1200 else tool_serialized[:1200] + "…"
            self.registry.memory.add("tool", compact, {"tool": name, "workspace": str(self.config.workspace)})
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
