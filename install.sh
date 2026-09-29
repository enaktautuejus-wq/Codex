#!/data/data/com.termux/files/usr/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
PREFIX_DIR="${PREFIX:-/data/data/com.termux/files/usr}"
BIN_DIR="$PREFIX_DIR/bin"

if [ ! -x "$PREFIX_DIR/bin/python" ]; then
    echo "Python tidak ditemukan. Jalankan: pkg install python"
    exit 1
fi

mkdir -p "$BIN_DIR"
LAUNCHER="$BIN_DIR/codex"
cat > "$LAUNCHER" <<EOF2
#!/data/data/com.termux/files/usr/bin/sh
set -eu
exec python "$ROOT_DIR/codex.py" "\$@"
EOF2
chmod 755 "$LAUNCHER"

echo "androidPE terpasang sebagai: codex"
echo "Jalankan: codex"
