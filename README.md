# Codex Termux Agent

OpenAI-compatible terminal coding/project agent for Termux. Python standard library only.

## Install

```bash
pkg update
pkg install python git ripgrep
termux-setup-storage
git clone <your-repository>.git
cd Codex
python codex.py
```

## Startup

1. Enter Base URL, API key, and model ID.
2. API is verified.
3. Enter the real project/workspace path, for example `/storage/emulated/0/Projects/MyProject`.
4. Codex changes into that directory and scans the project before the interactive screen opens.
5. If the directory is empty, the scan is effectively instant and the agent can start.

## Built-in agent capabilities

- read/write/edit/patch/grep/glob/list
- bash with destructive-command confirmation
- webfetch/websearch
- todo/task/background jobs
- project indexing and project scan
- persistent deep local memory in `.codex/memory.jsonl`
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

- `CODEX_MAX_TOKENS=2048`
- `CODEX_TEMPERATURE=0.15`
- `CODEX_STREAM=1`

Example:

```bash
CODEX_MAX_TOKENS=4096 python codex.py
```

Streaming improves perceived latency, while parallel independent tool calls reduce tool-loop latency. Actual model/provider latency still depends on the remote API.

## Safety and provider behavior

The application does not add a keyword-based refusal layer. It cannot disable or bypass policies imposed by the remote model or API provider. Destructive local operations are protected by explicit confirmation.

## Tests

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```
