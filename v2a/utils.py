# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — video to wechat article. Local-first pipeline utilities."""

from __future__ import annotations

import logging
import os
import sys

LOG = logging.getLogger("v2a")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[v2a] %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # keep Hugging Face / transformers chatter quiet by default
    if not verbose:
        for noisy in ("huggingface_hub", "transformers", "urllib3"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def find_ffmpeg(cfg_ffmpeg: str = "") -> str:
    """Resolve an ffmpeg executable: config value > PATH."""
    if cfg_ffmpeg and os.path.isfile(cfg_ffmpeg):
        return cfg_ffmpeg
    import shutil
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError(
            "ffmpeg not found. Install it and add to PATH (https://www.gyan.dev/ffmpeg/builds/), "
            "or set `ffmpeg: <path>` in the config file."
        )
    return exe


def fmt_ts(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}"


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
