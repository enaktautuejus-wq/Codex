# Codex Termux Agent

OpenAI-compatible terminal coding/project agent for Termux. Python standard library only.

## Install

```bash
pkg update
pkg install python git ripgrep
termux-setup-storage
git clone https://github.com/enaktautuejus-wq/Codex.git
cd Codex
python codex.py
```

## Startup

### First run

1. Enter Base URL, API key, and model ID.
2. API is verified once.
3. Credentials are saved globally in `~/.codex/config.json` (mode 600 when supported).
4. Enter the project/workspace path, for example `/storage/emulated/0/Projects/MyProject`.
5. Codex changes into that directory and scans the project before the interactive screen opens.

### Later runs

1. Saved Base URL/API key/model are reused automatically.
2. Only enter the project/workspace path.
3. Codex opens the home screen.

Use `/edit` inside Codex to edit the saved API key.

## Built-in agent capabilities

- read/write/edit/patch/delete/grep/glob/list
- bash with destructive-command confirmation
- webfetch/websearch
- todo/task/background jobs
- project indexing and project scan
- persistent project/session memory outside the workspace at `~/.codex/projects/<project-id>/memory.jsonl`
- Git status/diff/log inspection
- local checkpoints with restore confirmation
- environment/tool diagnosis through an internal `doctor` tool
- LSP availability/analysis adapter
- native OpenAI-compatible tool calls with JSON fallback
- parallel execution of independent native tool calls
- streaming SSE responses when the gateway supports OpenAI-compatible streaming
- automatic retry for transient HTTP/network failures
- Markdown code blocks with syntax-aware ANSI highlighting for many languages

## Interactive commands

The UI intentionally stays small. The agent has the diagnostic, memory, project, Git, checkpoint, todo, LSP, and background capabilities as tools, so it can invoke them itself.

- `/exit` or `/quit` — exit
- `/clear` — clear conversational context
- `/pwd` — show current workspace
- `/cd <path>` — switch workspace and automatically rescan it

## Performance

Defaults are optimized for latency:

- output/context token limits are controlled by the selected provider/model; Codex does not impose a fixed max-token cap
- `CODEX_TEMPERATURE=0.15`
- `CODEX_STREAM=1`

Streaming uses incremental SSE reads and a small output buffer so long responses do not flush every token.

Streaming improves perceived latency, while parallel independent tool calls reduce tool-loop latency. Actual model/provider latency still depends on the remote API.

## Safety and provider behavior

The application does not add a keyword-based refusal layer. It cannot disable or bypass policies imposed by the remote model or API provider. Destructive local operations are protected by explicit confirmation.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```

## Storage & provider limits

- Codex does not impose a fixed model context/output-token limit. The selected provider/model controls those limits.
- If the provider reports a context-length error, Codex compacts older conversation turns and retries while preserving the system prompt, current goal, project facts, decisions, and recent tool results.
- Persistent AI memory is stored outside the active workspace by default at `~/.codex/projects/<project-id>/memory.jsonl` (override the root with `CODEX_HOME`).
- The banner does not display the API key, Base URL, model ID, or workspace path.

## Faster streaming

The SSE reader uses incremental reads instead of waiting for large buffered chunks. Native tool calls can stream normally; the JSON fallback tool protocol is kept off the live UI so tool JSON does not appear as messy assistant output.

## Code rendering

Markdown fenced blocks are rendered as terminal code panels with language detection, syntax coloring, line numbers, and optional folding. Completed code fences are rendered exactly once during streaming, preventing HTML/CSS/JavaScript/etc. from leaking out as raw text.

## Jack runtime additions

- `/new` starts a fresh AI session. Previous conversation/tool memory is not loaded into the new session.
- Durable project knowledge is kept separately under `~/.codex/projects/<project-id>/memory.jsonl`.
- Assistant responses are rendered from the complete response to prevent Markdown fence/code leakage across streaming chunks.
- The large banner is now `Jack` with a red/black terminal style.
- Runtime telemetry reports request count, provider-reported token usage, latency, and rate-limit headers when available.
- Context/output limits are not hard-coded by Codex; provider/model limits and provider errors drive compaction/retry behavior.
- Verification is task-aware and is not forced for non-build/non-test work.
