# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — extract audio track from video with ffmpeg (local, free)."""

from __future__ import annotations

import os
import subprocess

from .utils import LOG


def extract_audio(
    video_path: str,
    out_wav: str,
    ffmpeg: str,
    sample_rate: int = 16000,
    channels: int = 1,
) -> str:
    """Extract the audio track to a 16 kHz mono PCM wav. Returns wav path."""
    video_path = os.path.abspath(video_path)
    out_wav = os.path.abspath(out_wav)
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"video not found: {video_path}")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", video_path,
        "-vn", "-ac", str(channels), "-ar", str(sample_rate),
        "-c:a", "pcm_s16le", out_wav,
    ]
    LOG.info("extracting audio: %s -> %s", os.path.basename(video_path), os.path.basename(out_wav))
    if os.environ.get("V2A_DEBUG_CMD"):
        print("DEBUG_CMD:", cmd, flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed for {video_path}:\n{r.stderr[-800:]}")
    if not os.path.isfile(out_wav) or os.path.getsize(out_wav) == 0:
        raise RuntimeError(f"ffmpeg produced no audio for {video_path} (video may be silent?)")
    return out_wav
