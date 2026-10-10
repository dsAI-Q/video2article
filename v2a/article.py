# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — turn subtitles into a WeChat official-account article.

This is the ONLY step that calls an LLM (online API or local Ollama).
Everything before this step is local and free.
"""

from __future__ import annotations

from .llm import make_client
from .styles import load_style, render_system_prompt


def generate_article(
    subtitle_text: str,
    style: str = "tutorial",
    cfg_llm: dict | None = None,
    extra_context: str = "",
) -> str:
    """Generate a markdown article from the subtitle text via LLM."""
    if not subtitle_text or not subtitle_text.strip():
        raise ValueError("subtitle text is empty — nothing to write an article from")

    style_cfg = load_style(style)
    system_prompt = render_system_prompt(style_cfg)

    user_parts = ["以下为视频字幕稿（含时间戳），请据此写公众号文章：\n", subtitle_text.strip()]
    if extra_context and extra_context.strip():
        user_parts.append(f"\n\n补充信息（供参考，不要照抄）:\n{extra_context.strip()}")

    client = make_client({"llm": cfg_llm or {}})
    return client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(user_parts)},
        ]
    )
