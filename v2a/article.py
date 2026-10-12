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

    user_parts = [
        "以下为视频字幕稿（含时间戳，ASR 自动转写），请据此写公众号文章：\n",
        subtitle_text.strip(),
        "\n\n注意：字幕是语音识别结果，可能有同音错别字。请根据上下文和 AI 领域常识自动纠正明显的识别错误，例如："
        "k1me/kimi/扣恩 → Qwen；美杰/美姐/美杰点一 → 2.1；"
        "拼音meji/以美几/一美几 → Qwen；"
        "其他明显语音识别错误也请自行修正，不要把错别字写进文章。",
    ]
    if extra_context and extra_context.strip():
        user_parts.append(f"\n\n补充信息（供参考，不要照抄）:\n{extra_context.strip()}")

    client = make_client({"llm": cfg_llm or {}})
    return client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "\n".join(user_parts)},
        ]
    )
