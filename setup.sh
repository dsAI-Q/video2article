#!/usr/bin/env bash
# ============================================================
#  v2a - one-click setup for Linux / macOS
#  Detects Python, then runs install.py in non-interactive mode.
# ============================================================
set -e
cd "$(dirname "$0")"

echo
echo "=== v2a setup (Linux/macOS) ==="
echo

PY=""
if command -v python3 >/dev/null 2>&1; then PY="python3"; fi
if [ -z "$PY" ] && command -v python >/dev/null 2>&1; then PY="python"; fi
if [ -z "$PY" ]; then
  echo "[ERROR] Python not found. Install Python 3.10+ first."
  exit 1
fi

if ! "$PY" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
  echo "[ERROR] Python too old (need 3.10+). Please upgrade Python."
  exit 1
fi
echo "[OK] Python: $("$PY" --version)"

echo
echo "Running install.py --yes ... (installs dependencies + ffmpeg, may take a few minutes)"
echo
"$PY" install.py --yes

echo
echo "=== Setup finished. Next: ==="
echo "  export LLM_API_KEY=sk-xxxx"
echo "  python3 -m v2a video your_video.mp4 --style tutorial"
