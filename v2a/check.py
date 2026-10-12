# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a.check — post-generation self-review for the article markdown.

Runs free, local, rule-based checks:
  - length sanity (too short => transcription likely failed; too long => may be padded)
  - leftover placeholders / TODO / 待补充 / template braces
  - heading structure (must start with #, must have ## sections)
  - web-mode: resource links block should be present
  - repeated / duplicated paragraphs (LLM sometimes loops)
  - obvious garbled / mojibake content

Returns a list of (severity, message). severity in {"error", "warning"}.
"""

from __future__ import annotations

import re


_PLACEHOLDER_RE = re.compile(r"(TODO|待补充|待完善|FIXME|XXX|\{[a-zA-Z_][a-zA-Z0-9_]*\})")
_HEADING_RE = re.compile(r"^#{1,3}\s", re.MULTILINE)
_TITLE_RE = re.compile(r"^#\s+\S+", re.MULTILINE)


def _count_chinese(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def check_article(text: str, web_mode: bool = False, video_title: str = "") -> list:
    """Return list of (severity, message) issues found in the article markdown."""
    issues: list = []
    if not text or not text.strip():
        return [("error", "article is empty")]

    total_chars = len(text)
    cn_chars = _count_chinese(text)

    # --- length sanity ---
    if cn_chars < 200:
        issues.append(("error",
            f"article has only {cn_chars} Chinese chars (<200): transcription likely failed "
            "or LLM produced a stub; check subtitles/LLM response"))
    elif cn_chars < 500:
        issues.append(("warning",
            f"article is short ({cn_chars} Chinese chars); expected ~1500-2500 for a full video"))
    elif cn_chars > 6000:
        issues.append(("warning",
            f"article is very long ({cn_chars} Chinese chars); may be padded or repeated"))

    # --- placeholders / TODO / template braces ---
    ph = _PLACEHOLDER_RE.findall(text)
    if ph:
        issues.append(("error",
            f"leftover placeholders detected: {sorted(set(ph))}"))

    # --- heading structure ---
    if not _TITLE_RE.search(text):
        issues.append(("warning", "article does not start with a top-level # title"))
    n_h2 = len(re.findall(r"^##\s+", text, re.MULTILINE))
    if n_h2 < 2:
        issues.append(("warning",
            f"only {n_h2} H2 sections; a normal tutorial article has 4-8 sections"))

    # --- web mode: resource links block ---
    if web_mode and "本期分享资料" not in text and "资源链接详见文末" not in text:
        issues.append(("warning",
            "web-mode article has no '本期分享资料' resource links section appended"))

    # --- repeated paragraphs (LLM loops) ---
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 40]
    seen = {}
    for p in paragraphs:
        key = p[:60]
        seen[key] = seen.get(key, 0) + 1
    dups = [k for k, c in seen.items() if c >= 3]
    if dups:
        issues.append(("warning",
            f"{len(dups)} paragraph(s) appear 3+ times (possible LLM loop): e.g. '{dups[0][:50]}...'"))

    # --- mojibake / garbled ---
    weird = len(re.findall(r"[�ï»¿ÃÂâ€œâ€]", text))
    if weird >= 5:
        issues.append(("error", f"possible mojibake/garbled text ({weird} bad chars)"))

    # --- empty trailing / suspicious tail ---
    if text.rstrip().endswith("```") and text.count("```") % 2 != 0:
        issues.append(("warning", "unclosed code fence in article"))

    # --- video title consistency ---
    if video_title:
        # Extract key entities from video title: uppercase words, model names, numbers
        title_entities = set(re.findall(r"[A-Z][a-zA-Z0-9]+(?:[.\-][0-9]+)?", video_title))
        # known ASR-confusion pairs: if title says X but article still has Y (the ASR error), flag it
        asr_mistakes = {
            "Qwen": ["k1me", "kimi", "扣恩", "拼音meji", "以美几", "一美几", "美杰"],
            "Kimi": ["k1me", "qwen"],
            "Hunyuan": ["混元"],
        }
        for correct, wrong_list in asr_mistakes.items():
            # if title mentions the correct model name
            if correct.lower() in video_title.lower() or correct in title_entities:
                for w in wrong_list:
                    if w.lower() in text.lower():
                        issues.append(("error",
                            f"文章与视频标题不一致：标题提到「{correct}」，但正文仍有 ASR 识别错误「{w}」，请修正"))
        # also: entities in title should appear somewhere in article
        missing = []
        for ent in title_entities:
            if len(ent) >= 3 and ent.lower() not in text.lower():
                missing.append(ent)
        if len(missing) >= 2:
            issues.append(("warning",
                f"视频标题中的关键信息 {missing[:5]} 在文章中未出现，可能内容偏离主题"))

    return issues


def format_report(issues: list) -> str:
    """Format issues into a human-readable report block."""
    if not issues:
        return "[v2a check] OK — no issues found"
    lines = [f"[v2a check] {len(issues)} issue(s):"]
    for sev, msg in issues:
        marker = "✗" if sev == "error" else "⚠"
        lines.append(f"  {marker} [{sev}] {msg}")
    return "\n".join(lines)
