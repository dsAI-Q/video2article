# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a CLI — video to WeChat official-account article.

Usage:
  python -m v2a transcribe <video-or-dir> [-o out.md] [--config cfg.yaml]
  python -m v2a video      <video-or-dir> [-o out.md] [--style tutorial] [--context ".."]
  python -m v2a article    <subtitles.md> [-o out.md] [--style tutorial]
  python -m v2a styles
  python -m v2a env        # print effective configuration

Environment overrides: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / V2A_STYLE
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .config import Config
from .styles import list_styles
from .utils import LOG, setup_logging


def _env_status() -> dict:
    """Lightweight environment probe: which pieces are missing."""
    import importlib.util

    status = {"python": True, "pip": True, "ffmpeg": True, "qwen_asr": False, "model": False}
    try:
        import v2a.utils as U
        status["ffmpeg"] = bool(U.find_ffmpeg(""))
    except Exception:  # noqa: BLE001
        status["ffmpeg"] = False

    if importlib.util.find_spec("qwen_asr"):
        status["qwen_asr"] = True

    try:
        from .utils import detect_model
        status["model"] = detect_model() is not None
    except Exception:  # noqa: BLE001
        status["model"] = False
    return status


def maybe_auto_install(no_install: bool) -> None:
    """If the environment is incomplete and auto-install is allowed, run
    install.py --yes (non-interactive) to install dependencies and ffmpeg."""
    missing = []
    try:
        st = _env_status()
        if not st["qwen_asr"]:
            missing.append("R2T2 backend (qwen-asr)")
        if not st["ffmpeg"]:
            missing.append("ffmpeg")
        if not st["model"]:
            missing.append("R2T2 model (3.8GB)")
    except Exception as e:  # noqa: BLE001
        LOG.warning("environment probe failed: %s", e)
        return

    if not missing:
        return
    LOG.warning("missing: %s", ", ".join(missing))
    if no_install:
        LOG.warning("auto-install disabled (--no-install); run `python install.py --yes` to set up")
        return
    if not sys.stdin.isatty():
        LOG.info("auto-installing dependencies (python install.py --yes)...")
    else:
        LOG.info("auto-installing dependencies (python install.py --yes)...")
    installer = Path(__file__).resolve().parent.parent / "install.py"
    if not installer.is_file():
        LOG.warning("install.py not found next to the package; skip auto-install")
        return
    try:
        r = subprocess.run([sys.executable, str(installer), "--yes"], cwd=str(installer.parent))
        if r.returncode != 0:
            LOG.error("auto-install exited with code %d — see messages above", r.returncode)
        else:
            LOG.info("auto-install finished. Re-checking...")
            st2 = _env_status()
            if not (st2["qwen_asr"] and st2["ffmpeg"]):
                LOG.warning("still missing: %s",
                            ", ".join(k for k, v in st2.items() if v is False and k in ("qwen_asr", "ffmpeg")))
            if not st2["model"]:
                LOG.warning("model still missing — follow the download commands printed above")
    except Exception as e:  # noqa: BLE001
        LOG.error("auto-install failed: %s", e)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="v2a", description=__doc__)
    p.add_argument("--config", default="", help="path to config yaml")
    p.add_argument("--no-install", action="store_true",
                   help="disable automatic dependency installation on startup")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("transcribe", help="video(s) -> timestamped subtitles (local, free)")
    sp.add_argument("input", help="video/audio file or directory")
    sp.add_argument("-o", "--output", default="", help="output markdown path")

    sp = sub.add_parser("video", help="full pipeline: video -> subtitles -> article (LLM for article only)")
    sp.add_argument("input", help="video/audio file or directory")
    sp.add_argument("-o", "--output", default="")
    sp.add_argument("--style", default="", help="article style (see `v2a styles`)")
    sp.add_argument("--context", default="", help="extra context for the article (e.g. video title, audience)")

    sp = sub.add_parser("article", help="subtitles markdown -> article (calls LLM)")
    sp.add_argument("input", help="subtitles markdown file")
    sp.add_argument("-o", "--output", default="")
    sp.add_argument("--style", default="", help="article style")

    sub.add_parser("styles", help="list available article styles")

    args = p.parse_args(argv)
    setup_logging(args.verbose)

    # auto-deploy: install missing dependencies/ffmpeg on first run (unless disabled)
    if args.cmd not in ("styles", "env"):
        maybe_auto_install(no_install=args.no_install)

    try:
        cfg = Config.load(args.config)
    except Exception as e:  # noqa: BLE001
        LOG.error("config load failed: %s", e)
        return 1

    if args.cmd == "styles":
        for s in list_styles():
            print(s)
        return 0

    try:
        if args.cmd == "transcribe":
            from v2a.pipeline import run_transcribe
            out = run_transcribe(args.input, cfg, args.output)
            print(out)
            return 0
        if args.cmd == "article":
            from v2a.article import generate_article
            with open(args.input, encoding="utf-8") as f:
                text = f.read()
            style = args.style or cfg.raw.get("style", "tutorial")
            article = generate_article(text, style=style, cfg_llm=cfg.raw.get("llm", {}))
            out = args.output or os.path.join(os.path.abspath(cfg.raw.get("output_dir", "output")), "article.md")
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                f.write(article)
            print(out)
            return 0
        if args.cmd == "video":
            from v2a.pipeline import run_video
            style_override = args.style or cfg.raw.get("style", "tutorial")
            cfg.raw["style"] = style_override
            out = run_video(args.input, cfg, extra_context=args.context)
            print(out)
            return 0
    except KeyboardInterrupt:
        LOG.info("interrupted")
        return 130
    except Exception as e:  # noqa: BLE001
        LOG.error("%s: %s", type(e).__name__, e)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
