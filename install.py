# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — one-click installer / environment doctor (pure stdlib, cross-platform).

What it does:
  1. checks Python version (>= 3.10)
  2. installs Python dependencies (requirements.txt + qwen-asr R2T2 backend)
  3. finds or downloads a portable ffmpeg (no admin rights needed)
  4. detects the R2T2 model (ComfyUI models dir / config / local dir) and prints
     mainland-friendly download commands if missing (hf-mirror / ModelScope)
  5. probes GPU and writes a ready-to-use config.yaml

Usage:
  python install.py              interactive
  python install.py --yes        accept defaults, no prompts
  python install.py --check-only check environment only (no changes)
  python install.py --dry-run    print what would be done, change nothing

Notes:
  - only the Python install itself and NVIDIA drivers cannot be automated;
    the script will tell you exactly what to do for those.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO_ID = "netease-youdao/Confucius4-R2T2"
QWEN_ASR = "qwen-asr==0.0.6"
PYTHON_MIN = (3, 10)
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


# ---------------------------------------------------------------- io helpers

def _say(msg: str = "") -> None:
    print(msg)


def _ask(question: str, default: bool = True) -> bool:
    """Ask yes/no. If stdin is not a tty (CI/pipe), fall back to `default`."""
    try:
        if not sys.stdin.isatty():
            return default
    except Exception:
        return default
    hint = "Y/n" if default else "y/N"
    ans = input(f"{question} [{hint}] ").strip().lower()
    if not ans:
        return default
    return ans in ("y", "yes")


def _run(cmd: list, **kw) -> subprocess.CompletedProcess:
    _say("  $ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, **kw)


# ---------------------------------------------------------------- checks

def check_python() -> bool:
    v = sys.version_info[:2]
    ok = v >= PYTHON_MIN
    _say(f"[1/5] Python: {platform.python_version()} ({'OK' if ok else 'TOO OLD'})")
    if not ok:
        _say("      Please install Python 3.10+ from https://www.python.org/downloads/")
    return ok


def check_pip() -> bool:
    try:
        r = _run([sys.executable, "-m", "pip", "--version"], capture_output=True, text=True)
        ok = r.returncode == 0
        _say(f"[2/5] pip: {'OK' if ok else 'MISSING'}")
        if not ok:
            _say("      Run: python -m ensurepip --upgrade")
        return ok
    except Exception as e:  # noqa: BLE001
        _say(f"      pip check failed: {e}")
        return False


def pip_install(requirements: Path, extra: list[str], yes: bool) -> None:
    base = [sys.executable, "-m", "pip", "install"]
    _say("  installing core dependencies (librosa/soundfile/pyyaml/numpy)...")
    if yes or _ask("  install core dependencies now?", default=True):
        _run(base + ["-r", str(requirements)])
    _say(f"  installing R2T2 backend ({QWEN_ASR})...")
    _say("  NOTE: qwen-asr pins transformers==4.57.6 (may downgrade a newer one)")
    if yes or _ask("  install R2T2 backend (recommended)?", default=True):
        _run(base + extra)


# ---------------------------------------------------------------- ffmpeg

def find_ffmpeg() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # portable copy inside project, if previously installed by this script
    for probe in ("ffmpeg", "bin/ffmpeg"):
        p = Path(__file__).resolve().parent / ".bin" / probe
        if os.name == "nt":
            p = p.with_suffix(".exe")
        if p.is_file():
            return str(p)
    return ""


def download_ffmpeg(target_dir: Path, yes: bool) -> str:
    """Download a portable ffmpeg zip and extract it under target_dir. Returns ffmpeg path."""
    if yes or _ask("  download a portable ffmpeg into the project (no admin needed)?", default=True):
        zip_path = target_dir / "ffmpeg.zip"
        _say(f"  downloading ffmpeg from {FFMPEG_URL} ...")
        try:
            urllib.request.urlretrieve(FFMPEG_URL, zip_path)
        except Exception as e:  # noqa: BLE001
            _say(f"  download failed: {e}")
            _say("  hint: try again with a proxy, or install ffmpeg manually and add it to PATH")
            return ""
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(target_dir / "ffmpeg")
        zip_path.unlink(missing_ok=True)
        for f in (target_dir / "ffmpeg").rglob("ffmpeg.exe" if os.name == "nt" else "ffmpeg"):
            return str(f)
    return ""


def check_ffmpeg(dry: bool, yes: bool) -> str:
    exe = find_ffmpeg()
    if exe:
        _say(f"[3/5] ffmpeg: found ({exe})")
        return exe
    _say("[3/5] ffmpeg: NOT FOUND")
    if dry:
        _say("  (dry-run) would download portable ffmpeg into .bin/")
        return ""
    if os.name == "nt":
        return download_ffmpeg(Path(__file__).resolve().parent / ".bin", yes)
    _say("  install it with your package manager, e.g.:")
    _say("    apt install ffmpeg   (Debian/Ubuntu)")
    _say("    brew install ffmpeg  (macOS)")
    return ""


# ---------------------------------------------------------------- model

def check_model(dry: bool, yes: bool) -> str:
    try:
        from v2a.utils import detect_model
        mdl = detect_model()
    except Exception:  # noqa: BLE001
        mdl = None
    if mdl:
        _say(f"[4/5] R2T2 model: found ({mdl})")
        return str(mdl)
    _say("[4/5] R2T2 model: NOT FOUND")
    if dry:
        _say("  (dry-run) would print download commands")
        return ""
    target = Path(__file__).resolve().parent / "models" / "r2t2" / "netease-youdao" / "Confucius4-R2T2"
    print_model_download_hints(target)
    if yes or _ask("  download the model now (may take long)?", default=False):
        _say("  automatic model download is not bundled; please run one of the commands above")
    return str(target)


def print_model_download_hints(target: Path) -> None:
    t = target.resolve()
    _say("  R2T2 model (~3.8GB) download commands (pick one):")
    _say(f"    # option A - mainland mirror (recommended, no proxy)")
    _say(f"    HF_ENDPOINT=https://hf-mirror.com huggingface-cli download {REPO_ID} --local-dir {t}")
    _say(f"    # option B - ModelScope (mainland, no proxy)")
    _say(f"    pip install modelscope && modelscope download --model {REPO_ID} --local_dir {t}")
    _say(f"    # option C - direct / via proxy")
    _say(f"    huggingface-cli download {REPO_ID} --local-dir {t}")
    _say("  after downloading, re-run: python install.py --check-only")


# ---------------------------------------------------------------- gpu / config

def check_gpu() -> bool:
    try:
        r = _run(
            [sys.executable, "-c", "import torch; print(torch.cuda.is_available())"],
            capture_output=True, text=True, timeout=120,
        )
        ok = r.stdout.strip().lower() == "true"
    except Exception:  # noqa: BLE001
        ok = False
    _say(f"[5/5] GPU (CUDA): {'available' if ok else 'not detected -> CPU mode (slower but works)'}")
    return ok


def _yaml_path(p: str) -> str:
    """Return a YAML-safe absolute path (forward slashes work on Windows too)."""
    return p.replace("\\", "/")


def write_config(model_path: str, ffmpeg: str, gpu: bool, force: bool = False) -> Path:
    cfg = Path(__file__).resolve().parent / "config.yaml"
    if cfg.is_file() and not force:
        _say(f"  config.yaml already exists (kept): {cfg}")
        return cfg
    lines = [
        "llm:",
        "  base_url: https://api.deepseek.com/v1",
        '  api_key: ""            # or set env LLM_API_KEY',
        "  model: deepseek-chat",
        "asr:",
        "  backend: auto",
        f'  model_path: "{_yaml_path(model_path)}"',
        "  device: auto",
        "  max_segment_seconds: 30",
        f'ffmpeg: "{_yaml_path(ffmpeg)}"',
        "style: tutorial",
        "",
    ]
    cfg.write_text("\n".join(lines), encoding="utf-8")
    _say(f"  wrote config.yaml (model_path={model_path}, device={'cuda:0' if gpu else 'cpu'})")
    return cfg


# ---------------------------------------------------------------- main

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--yes", action="store_true", help="accept defaults, no prompts")
    p.add_argument("--check-only", action="store_true", help="only inspect, change nothing")
    p.add_argument("--dry-run", action="store_true", help="print what would be done, change nothing")
    args = p.parse_args()

    _say("=" * 62)
    _say("v2a installer — video to WeChat article")
    _say("=" * 62)

    ok = True
    ok &= check_python()
    ok &= check_pip()
    if not ok:
        _say("\nPlease fix the items above and re-run.")
        return 1

    if args.check_only:
        ff = check_ffmpeg(dry=True, yes=args.yes)
        mdl = check_model(dry=True, yes=args.yes)
        gpu = check_gpu()
        _say("\nEnvironment check done. Install missing items then re-run with --check-only.")
        return 0

    dry = args.dry_run
    if not dry:
        pip_install(Path(__file__).resolve().parent / "requirements.txt", [QWEN_ASR], args.yes)
    else:
        _say("[2/5] (dry-run) would pip install -r requirements.txt + " + QWEN_ASR)

    ff = check_ffmpeg(dry=dry, yes=args.yes)
    mdl = check_model(dry=dry, yes=args.yes)
    gpu = check_gpu()

    if not dry:
        write_config(mdl, ff, gpu)
    else:
        _say("  (dry-run) would write config.yaml")

    _say("\n" + "=" * 62)
    _say("Next steps:")
    _say("  set LLM_BASE_URL / LLM_API_KEY / LLM_MODEL (or edit config.yaml)")
    _say("  python -m v2a video your_video.mp4 --style tutorial")
    _say("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
