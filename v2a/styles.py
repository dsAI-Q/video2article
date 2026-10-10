# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — WeChat official-account article styles (local templates, no LLM).

Styles live in the `styles/` directory as YAML files. `custom.md` can be used
to supply a completely free-form writing guideline.
"""

from __future__ import annotations

import os

import yaml

_STYLES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "styles")


def list_styles() -> list:
    names = []
    for f in os.listdir(_STYLES_DIR):
        if f.endswith(".yaml"):
            names.append(f[:-5])
    return sorted(names)


def load_style(name: str) -> dict:
    """Load a style template by name (e.g. 'tutorial'). Falls back to default."""
    name = (name or "").strip().lower()
    path = os.path.join(_STYLES_DIR, f"{name}.yaml") if name else ""
    if not path or not os.path.isfile(path):
        path = os.path.join(_STYLES_DIR, "tutorial.yaml")
        if not os.path.isfile(path):
            raise FileNotFoundError(f"no style templates found under {_STYLES_DIR}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def render_system_prompt(style: dict) -> str:
    """Build the system prompt from a style template."""
    lines = [
        "你是一名资深微信公众号编辑，请根据下方字幕稿写一篇可直接发布的公众号文章。",
        "要求：原创、通顺、有信息量，符合公众号阅读习惯（短段落、小标题、适当口语化）；",
        "不要使用 Markdown 代码块或```，不要输出与文章无关的解释。",
    ]
    if style.get("title_rule"):
        lines.append(f"标题要求：{style['title_rule']}")
    if style.get("tone"):
        lines.append(f"语气与文风：{style['tone']}")
    if style.get("structure"):
        lines.append("文章结构：")
        for i, part in enumerate(style["structure"], 1):
            lines.append(f"  {i}. {part}")
    if style.get("format_notes"):
        lines.append(f"排版要求：{style['format_notes']}")
    if style.get("extra"):
        lines.append(style["extra"])
    lines.append("输出格式：先给 1 个主标题（以 # 开头），再给 1-2 个备选标题（以 ## 开头），空一行后输出正文。")
    return "\n".join(lines)
