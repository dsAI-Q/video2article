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
import sys

from .config import Config
from .styles import list_styles
from .utils import LOG, setup_logging


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="v2a", description=__doc__)
    p.add_argument("--config", default="", help="path to config yaml")
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
