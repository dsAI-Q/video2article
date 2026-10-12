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

def fetch_from_url(url: str, out_dir: str, keep_video: bool = False) -> dict:
    """Return dict(title, subtitle_path, audio_path, video_path, source_url).

    Exactly one of subtitle_path / audio_path is set (subtitle wins when both
    exist). When keep_video=True, the full video (bestvideo+bestaudio merged
    to mp4) is also downloaded and returned in video_path.
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
        "proxy": "",  # bypass system proxy for domestic Bilibili
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
            "video_path": "",
            "source_url": url,
        }

    # --- Pass 2: no subtitles -> download best audio (+ optional full video) ---
    LOG.info("no CC subtitles on page; downloading audio stream%s...",
              " (and full video)" if keep_video else "")
    if keep_video:
        # best video + best audio, merge to mp4 (needs ffmpeg, already required by v2a)
        audio_opts = {
            "format": "bestvideo*+bestaudio/best",
            "merge_output_format": "mp4",
            "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
    else:
        audio_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(out_dir, "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "proxy": "",  # Bilibili is a domestic site — bypass any system proxy
        }
    audio_path = ""
    video_path = ""
    with yt_dlp.YoutubeDL(audio_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", title)
        vid = info["id"]
        if keep_video:
            # merged mp4
            for ext in ("mp4", "mkv", "webm"):
                cand = os.path.join(out_dir, f"{vid}.{ext}")
                if os.path.isfile(cand):
                    video_path = cand
                    break
        # audio file (m4a/webm/opus etc.) — used for ASR
        for ext in ("m4a", "webm", "mp3", "opus", "wav"):
            cand = os.path.join(out_dir, f"{vid}.{ext}")
            if os.path.isfile(cand):
                audio_path = cand
                break
    if not audio_path and not video_path:
        # fallback: search newest file in out_dir
        cands = sorted(Path(out_dir).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if cands:
            audio_path = str(cands[0])

    LOG.info("downloaded: video=%s audio=%s", video_path or "-", audio_path or "-")
    return {
        "title": title,
        "subtitle_path": "",
        "audio_path": audio_path,
        "video_path": video_path,
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


# ---------------------------------------------------------------------------
# 3. fetch video description + comments, extract resource links
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s<>\"'\)]+", re.IGNORECASE)


def extract_links(text: str) -> list:
    """Extract all http(s) URLs from text, preserving order, de-duplicated."""
    if not text:
        return []
    seen = set()
    out = []
    for m in _URL_RE.finditer(text):
        u = m.group(0).rstrip(".,;，。；")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _classify_link(url: str) -> str:
    """Roughly classify a link for grouping in the resources section."""
    u = url.lower()
    if any(k in u for k in ("pan.quark.cn", "pan.baidu.com", "aliyundrive", "alipan",
                            "lanzou", "lanzoui", "123pan", "xunlei", "uc.cn")):
        return "网盘下载"
    if "feishu" in u or "larksuite" in u or "docs.qq" in u:
        return "文档/教程"
    if "runninghub" in u or "runhub" in u:
        return "在线体验平台"
    if "bilibili" in u or "b23.tv" in u:
        return "B站"
    return "其他链接"


def fetch_metadata(url: str, max_comments: int = 50) -> dict:
    """Fetch video title, description and the AUTHOR'S pinned/resource comment.

    Returns dict(title, description, pinned_comment, links).
    Links are extracted from description + the author's own comment only
    (the UP主's resource-aggregating comment is usually the pinned one).
    """
    import re as _re
    import json as _json
    import urllib.request as _urq

    m = _re.search(r"(BV[0-9A-Za-z]{10})", url)
    if not m:
        return {"title": url, "description": "", "pinned_comment": "", "links": []}
    bvid = m.group(1)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.bilibili.com/",
    }
    opener = _urq.build_opener(_urq.ProxyHandler({}))  # bypass system proxy

    def _get(api_url):
        req = _urq.Request(api_url, headers=headers)
        with opener.open(req, timeout=15) as resp:
            return _json.loads(resp.read().decode("utf-8"))

    # 1) video info
    info = _get(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
    if info.get("code") != 0:
        LOG.warning("bilibili view api error: %s", info.get("message"))
        return {"title": url, "description": "", "pinned_comment": "", "links": []}
    d = info["data"]
    title = d.get("title", url)
    description = d.get("desc", "") or ""
    up_name = (d.get("owner") or {}).get("name", "")
    aid = d.get("aid", 0)

    # 2) comments (sort=2 => by time, pinned appears first)
    pinned = ""
    try:
        rep = _get(f"https://api.bilibili.com/x/v2/reply?type=1&oid={aid}&sort=2&pn=1&ps=10")
        rdata = rep.get("data") or {}
        author_comments = []
        # pinned comments are in top_replies, separate from replies
        for c in (rdata.get("top_replies") or []):
            text = (c.get("content") or {}).get("message", "")
            if text:
                author_comments.append(text)
        for c in (rdata.get("replies") or []):
            member = c.get("member") or {}
            author = member.get("uname", "")
            text = (c.get("content") or {}).get("message", "")
            if not text:
                continue
            if up_name and author == up_name:
                author_comments.append(text)
        if author_comments:
            pinned = max(author_comments, key=lambda t: len(_URL_RE.findall(t)))
            LOG.info("author/pinned comment found (%.0f chars, %d urls)",
                     len(pinned), len(_URL_RE.findall(pinned)))
    except Exception as e:
        LOG.warning("bilibili reply api failed: %s", e)

    blob = "\n".join(p for p in (description, pinned) if p)
    links = extract_links(blob)
    LOG.info("metadata: %d links extracted (from description + pinned comment)", len(links))
    return {"title": title, "description": description, "pinned_comment": pinned, "links": links}


def format_resources_section(links: list) -> str:
    """Format extracted links into a markdown '本期分享资料' block, grouped by type."""
    if not links:
        return ""
    groups = {}
    for u in links:
        cat = _classify_link(u)
        groups.setdefault(cat, []).append(u)
    lines = ["", "---", "", "## 本期分享资料", ""]
    order = ["网盘下载", "文档/教程", "在线体验平台", "B站", "其他链接"]
    for cat in order:
        if cat not in groups:
            continue
        lines.append(f"**{cat}**")
        for u in groups[cat]:
            lines.append(f"- {u}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
