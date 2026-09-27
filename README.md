# Codex Termux Agent

OpenAI-compatible coding/building agent designed for Termux.

## Requirements

- Termux
- Python 3.10+
- `curl` is optional; web tools use Python stdlib
- `rg` (ripgrep) is recommended for fast grep
- `git` is optional for repository work

## Install

```bash
pkg update
pkg install python git ripgrep
git clone <your-repository>.git
cd Codex
python codex.py
```

No third-party Python packages are required.

## Startup

API key sekarang dibaca dengan input Termux-friendly: karakter yang diketik/ditempel tampil sebagai `*`, jadi ada feedback visual tanpa menampilkan nilai key. Backspace dan Enter didukung.


```text
Base url: https://provider.example/v1
api key (ketik/tempel, tampil sebagai *): ********
id model: your-model

Verifikasi api: loading...
Verifikasi api: berhasil.

CODEX
api key: ****
base url: https://provider.example/v1
model: your-model

root@codex:~#
```

The API must expose an OpenAI-compatible `/chat/completions` endpoint.

## Tools

### Files
- `read(path, start_line?, end_line?)`
- `write(path, content)`
- `edit(path, old, new, count?)`
- `patch(path, diff)`
- `grep(pattern, path, flags?)`
- `glob(pattern, path?)`
- `list(path, pattern?)`

`read` supports text files, PDFs (text extraction when available through the Python stdlib fallback), and images by returning metadata. Image pixel OCR/vision is provider-dependent and is not silently fabricated.

### Execution
- `bash(command, cwd?, timeout?)`

### Web
- `webfetch(url)`
- `websearch(query, max_results?)`

Both use DuckDuckGo HTML for search. `webfetch` fetches the requested URL directly.

### Session management
- `todo(action, items?)`
- `task(prompt, role?)`
- `lsp(action, path, ...)`

## Security / execution model

The agent can operate on the directory from which it was launched. Shell commands are executed through Termux. Destructive shell commands are detected and require an explicit `CONFIRM` response inside the agent loop.

The model is not granted an imaginary capability: a tool succeeds only when the underlying Termux environment permits it.

## Commands

Inside Codex:

```text
/clear
/tools
/todo
/exit
/quit
```

`/clear` resets conversation history. `/tools` prints registered tools.

## Environment

Optional:

```bash
export CODEX_WORKSPACE="$HOME/Codex"
```

By default the current working directory is used.

