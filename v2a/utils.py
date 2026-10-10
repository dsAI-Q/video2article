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


# ---------------------------------------------------------------- model discovery

def candidate_model_dirs() -> list:
    """Candidate R2T2 checkpoint locations (ComfyUI models dir / project models)."""
    repo = os.path.join("r2t2", "netease-youdao", "Confucius4-R2T2")
    cands = []
    env = os.environ.get("COMFYUI_MODELS_DIR", "")
    if env:
        cands.append(os.path.join(env, repo))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cands.append(os.path.join(root, "ComfyUI", "models", repo))
    cands.append(os.path.join(root, "models", repo))
    cands.append(os.path.join(os.path.expanduser("~"), "ComfyUI", "models", repo))
    if os.name == "nt":
        for drive in ("C", "D", "E"):
            for base in (r"ComfyUI", r"Comfyui", r"ComfyUI-Windows_portable"):
                cands.append(os.path.join(f"{drive}:\\", base, "models", repo))
            # scan drive root for custom-named ComfyUI install dirs (e.g. Comfyui-dashengAI)
            droot = f"{drive}:\\"
            if os.path.isdir(droot):
                try:
                    for name in os.listdir(droot):
                        cands.append(os.path.join(droot, name, "ComfyUI", "models", repo))
                except OSError:
                    pass
    out, seen = [], set()
    for p in cands:
        s = os.path.normpath(p).lower()
        if s not in seen:
            seen.add(s)
            out.append(p)
    return out


def detect_model() -> str | None:
    """Return the first existing R2T2 checkpoint dir (needs config.json + model.safetensors)."""
    for p in candidate_model_dirs():
        if os.path.isfile(os.path.join(p, "config.json")) and \
           os.path.isfile(os.path.join(p, "model.safetensors")):
            return p
    return None
