# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a.web — fetch video subtitles or audio from a web page URL.

Strategy:
  1. Probe the page with yt-dlp. If CC / automatic subtitles exist (zh / en),
     download them directly (free, no ASR, near-perfect).
  2. If no subtitles are available, download bestaudio and fall back to the
     local R2T2 / Whisper pipeline.

Supports 1000+ sites via yt-dlp (Bilibili, YouTube, Douyin, Weibo, X, etc.).
Overseas sites (YouTube) need a proxy: set HTTPS_PROXY=http://127.0.0.1:7897
or pass --proxy in future.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .utils import LOG, fmt_ts


# ---------------------------------------------------------------------------
# 1. fetch subtitles or audio from URL
# ---------------------------------------------------------------------------

def fetch_from_url(url: str, out_dir: str) -> dict:
    """Return dict(title, subtitle_path, audio_path, source_url).

    Exactly one of subtitle_path / audio_path is set (subtitle wins when both
    exist).
    """
    try:
        import yt_dlp  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError(
            "yt-dlp is required for `v2a web`. Install it with:\n"
            "  pip install yt-dlp"
        ) from e

    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # Common subtitle languages we accept
    sub_langs = ["zh-Hans", "zh-CN", "zh", "en-US", "en"]

    # --- Pass 1: try subtitles only (skip download) ---
    probe_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": sub_langs,
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    subtitle_path = ""
    title = url
    try:
        with yt_dlp.YoutubeDL(probe_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        title = info.get("title", url)
        # Find downloaded subtitle file
        for lang in sub_langs:
            for ext in ("vtt", "srt"):
                cand = os.path.join(out_dir, f"{info['id']}.{lang}.{ext}")
                if os.path.isfile(cand):
                    subtitle_path = cand
                    break
            if subtitle_path:
                break
    except Exception as e:  # noqa: BLE001
        LOG.warning("subtitle probe failed (%s); will download audio instead", e)

    if subtitle_path:
        LOG.info("found webpage subtitles: %s", subtitle_path)
        return {
            "title": title,
            "subtitle_path": subtitle_path,
            "audio_path": "",
            "source_url": url,
        }

    # --- Pass 2: no subtitles -> download best audio ---
    LOG.info("no CC subtitles on page; downloading audio stream...")
    audio_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    audio_path = ""
    with yt_dlp.YoutubeDL(audio_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", title)
        # yt-dlp returns the actual downloaded filename under requested_downloads
        # or we reconstruct from id + expected ext
        vid = info["id"]
        for ext in ("m4a", "webm", "mp3", "opus", "wav"):
            cand = os.path.join(out_dir, f"{vid}.{ext}")
            if os.path.isfile(cand):
                audio_path = cand
                break
    if not audio_path:
        # fallback: search newest file in out_dir
        cands = sorted(Path(out_dir).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            audio_path = str(cands[0])

    LOG.info("audio downloaded: %s", audio_path)
    return {
        "title": title,
        "subtitle_path": "",
        "audio_path": audio_path,
        "source_url": url,
    }


# ---------------------------------------------------------------------------
# 2. parse vtt / srt -> our timestamped markdown
# ---------------------------------------------------------------------------

_TS_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})"
)


def _ts_to_sec(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_subtitle_file(path: str) -> list:
    """Parse .vtt or .srt -> list of (start_sec, end_sec, text)."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    segments = []
    # Normalize line endings
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    # Drop WEBVTT header lines
    blocks = re.split(r"\n\s*\n", raw)
    for block in blocks:
        m = _TS_RE.search(block)
        if not m:
            continue
        st = _ts_to_sec(*m.group(1, 2, 3, 4))
        en = _ts_to_sec(*m.group(5, 6, 7, 8))
        # text = everything after the timestamp line, stripped
        after = block[m.end():].strip()
        # Remove VTT tags like <c> or timestamp inline
        after = re.sub(r"<[^>]+>", "", after)
        after = re.sub(r"\d{2}:\d{2}:\d{2}[.,]\d{3} -->.*", "", after)
        after = "\n".join(line.strip() for line in after.splitlines() if line.strip())
        if after:
            segments.append((st, en, after))
    # Merge adjacent same-text duplicates (auto-captions often repeat)
    merged = []
    for st, en, txt in segments:
        if merged and merged[-1][2] == txt:
            prev_st, _, _ = merged[-1]
            merged[-1] = (prev_st, en, txt)
        else:
            merged.append((st, en, txt))
    return merged


def subtitle_markdown_from_web(title: str, source_url: str, segments: list) -> str:
    total = segments[-1][1] if segments else 0.0
    lines = [
        f"# {title}",
        f"来源网页: {source_url}",
        f"转写引擎: webpage-subtitles",
        f"总时长: {fmt_ts(total)}",
        "",
    ]
    for st, en, txt in segments:
        lines.append(f"## [{fmt_ts(st)} - {fmt_ts(en)}]")
        lines.append(txt)
        lines.append("")
    return "\n".join(lines)
