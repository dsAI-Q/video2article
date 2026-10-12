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
import re
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

    sp = sub.add_parser("web", help="fetch subtitles/audio from a web page URL (Bilibili/YouTube/...) and transcribe")
    sp.add_argument("url", help="video page URL")
    sp.add_argument("-o", "--output", default="", help="output markdown path")
    sp.add_argument("--style", default="", help="article style (default: subtitles only, no article)")
    sp.add_argument("--context", default="", help="extra context for article")
    sp.add_argument("--no-article", action="store_true", help="only produce subtitles, do not call LLM")
    sp.add_argument("--keep-video", action="store_true", help="also download the full mp4 video to output/")

    sub.add_parser("styles", help="list available article styles")

    sp = sub.add_parser("check", help="run post-generation self-review on an article markdown")
    sp.add_argument("input", help="article markdown file to review")
    sp.add_argument("--web-mode", action="store_true", help="also check for resource-links section")

    sub.add_parser("webui", help="launch local web UI (http://127.0.0.1:8765)")

    args = p.parse_args(argv)
    setup_logging(args.verbose)

    # auto-deploy: install missing dependencies/ffmpeg on first run (unless disabled)
    if args.cmd not in ("styles", "env"):
        maybe_auto_install(no_install=args.no_install)

    try:
        # Auto-load ./config.yaml when --config is not explicitly given.
        cfg_path = args.config or (os.path.join(os.getcwd(), "config.yaml"))
        if not os.path.isfile(cfg_path):
            cfg_path = ""
        cfg = Config.load(cfg_path)
    except Exception as e:  # noqa: BLE001
        LOG.error("config load failed: %s", e)
        return 1

    if args.cmd == "styles":
        for s in list_styles():
            print(s)
        return 0

    if args.cmd == "check":
        from v2a.check import check_article, format_report
        with open(args.input, encoding="utf-8") as f:
            text = f.read()
        issues = check_article(text, web_mode=args.web_mode)
        print(format_report(issues))
        # non-zero exit if any error-level issue
        return 1 if any(sev == "error" for sev, _ in issues) else 0

    if args.cmd == "webui":
        from v2a.webui import main as webui_main
        webui_main(cfg)
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
            # post-generation self-review
            from v2a.check import check_article, format_report
            issues = check_article(article, web_mode=False)
            print(format_report(issues))
            print(out)
            return 0
        if args.cmd == "video":
            from v2a.pipeline import run_video
            style_override = args.style or cfg.raw.get("style", "tutorial")
            cfg.raw["style"] = style_override
            out = run_video(args.input, cfg, extra_context=args.context)
            print(out)
            return 0
        if args.cmd == "web":
            from v2a.web import (
                fetch_from_url, parse_subtitle_file, subtitle_markdown_from_web,
                fetch_metadata, format_resources_section,
            )
            from v2a.pipeline import run_transcribe
            out_dir = os.path.abspath(cfg.raw.get("output_dir", "output"))
            os.makedirs(out_dir, exist_ok=True)
            LOG.info("fetching from: %s", args.url)
            info = fetch_from_url(args.url, out_dir, keep_video=args.keep_video)
            if info.get("video_path"):
                LOG.info("full video saved: %s", info["video_path"])
            safe_title = re.sub(r"[^\w\-_.\u4e00-\u9fff]+", "_", info["title"]).strip("_") or "web"

            if info["subtitle_path"]:
                # webpage already has CC subtitles -> parse directly
                segs = parse_subtitle_file(info["subtitle_path"])
                LOG.info("parsed %d subtitle segments from webpage", len(segs))
                md = subtitle_markdown_from_web(info["title"], args.url, segs)
                md_path = args.output or os.path.join(out_dir, f"{safe_title}_字幕.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md)
                LOG.info("subtitles saved -> %s", md_path)
            else:
                # no subtitles -> local ASR on downloaded audio
                md_path = run_transcribe(info["audio_path"], cfg, args.output)

            # Fetch description + comments, extract resource links (net disk, docs, platform)
            resources_block = ""
            try:
                meta = fetch_metadata(args.url)
                resources_block = format_resources_section(meta["links"])
                if meta["links"]:
                    LOG.info("extracted %d resource links from description/comments", len(meta["links"]))
            except Exception as e:  # noqa: BLE001
                LOG.warning("metadata/resource-link fetch failed: %s", e)

            if not args.no_article:
                from v2a.article import generate_article
                with open(md_path, encoding="utf-8") as f:
                    subtitle_text = f.read()
                style = args.style or cfg.raw.get("style", "tutorial")
                article = generate_article(
                    subtitle_text,
                    style=style,
                    cfg_llm=cfg.raw.get("llm", {}),
                    extra_context=args.context,
                )
                # Append resource links block verbatim (do not let LLM rewrite URLs)
                if resources_block:
                    article = article.rstrip() + "\n" + resources_block
                art_path = os.path.join(out_dir, f"{safe_title}_文章.md")
                with open(art_path, "w", encoding="utf-8") as f:
                    f.write(article)
                # post-generation self-review (web mode: expect resource links block)
                from v2a.check import check_article, format_report
                issues = check_article(article, web_mode=True)
                print(format_report(issues))
                LOG.info("article saved -> %s", art_path)
                print(art_path)
                return 0

            # --no-article: also save extracted links alongside subtitles
            if resources_block:
                links_path = os.path.join(out_dir, f"{safe_title}_资源链接.md")
                with open(links_path, "w", encoding="utf-8") as f:
                    f.write(resources_block)
                LOG.info("resource links saved -> %s", links_path)
            print(md_path)
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
