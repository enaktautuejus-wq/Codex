# Codex Termux Agent

Agent coding terminal untuk Termux dengan workspace proyek yang dipilih saat startup.

## Fitur

- OpenAI-compatible `/chat/completions` API.
- Setup: Base URL -> API key masked -> Model ID -> **Path folder proyek**.
- Setelah verifikasi API berhasil, program menjalankan `cd`/`os.chdir()` ke folder proyek dan membuka UI Codex.
- File tools: `read`, `write`, `edit`, `patch`, `grep`, `glob`, `list`.
- Execution: `bash`.
- Web: `webfetch`, `websearch` (DuckDuckGo HTML).
- Agent: `todo`, `task`, `lsp` adapter.
- Native OpenAI-compatible function/tool calling jika gateway mendukungnya.
- Fallback otomatis ke strict JSON tool protocol jika native tool calling ditolak gateway.
- Retry terbatas untuk error koneksi, timeout, rate limit, dan HTTP 5xx.
- Project-aware workflow: inspect -> edit -> test/build -> verify -> report.
- Workspace isolation untuk operasi file.
- `/cd <path>` untuk mengganti workspace selama sesi.
- `/pwd`, `/tools`, `/todo`, `/clear`, `/exit`, `/quit`.
- Destructive shell command tetap membutuhkan `CONFIRM <command>`.

## Install di Termux

```bash
pkg update
pkg install python git ripgrep
termux-setup-storage
```

Clone repository kamu, lalu:

```bash
git clone <repository-url>
cd Codex
python codex.py
```

Saat startup:

```text
Base url: https://api.example.com/v1
api key: ****************
id model: your-model
Verifikasi api: loading...
Verifikasi api: berhasil.
Path folder: /storage/emulated/0/Projects/MyProject
Workspace aktif. Membuka Codex...
```

Setelah itu semua tool file memakai folder proyek tersebut sebagai root.

## Instruction-following

Agent diarahkan untuk memprioritaskan tujuan user, menggunakan tools ketika diperlukan, melakukan pekerjaan secara bertahap, memulihkan error teknis yang bisa dipulihkan, dan memverifikasi hasil. Aplikasi tidak menambahkan refusal layer berdasarkan kata kunci.

Namun agent tidak dapat secara jujur menjamin bahwa remote model/provider akan mengabaikan kebijakan mereka. Respons refusal dari remote API tetap ditampilkan sebagai respons remote API.

## Keamanan operasional

Perintah shell yang terdeteksi berpotensi destruktif seperti `rm -rf`, `mkfs`, `dd if=`, `git reset --hard`, `git clean -fd`, `shutdown`, dan `reboot` meminta konfirmasi eksplisit. Ini mencegah agent melakukan perubahan besar secara tidak sengaja.

API key tidak disimpan ke file konfigurasi oleh aplikasi.
