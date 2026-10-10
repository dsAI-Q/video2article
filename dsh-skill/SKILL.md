---
name: video2article
description: 视频转公众号文章（v2a）。本地教学/分享视频批量转带时间戳字幕，再用大模型生成公众号文章；仅成文一步调 LLM。用户说"视频转文字/转公众号文章/提取视频字幕/批量出文章"时使用。
---

# v2a — 视频转公众号文章

本 skill 对应仓库根目录（即本 `dsh-skill/` 的上一级）。**所有命令都在仓库根目录执行。**

## 流程（费用最小化）

1. 提取：ffmpeg → 16kHz 单声道 wav（本地）
2. 转写：R2T2（默认）或 Whisper 本地 ASR，VAD 静音分段 → 带时间戳 Markdown 字幕（本地，免费）
3. 成文：仅此步调 LLM（DeepSeek / 豆包等 OpenAI 兼容 API，或本地 Ollama）→ 公众号文章

## 首次使用前

```bash
cd <本仓库根目录>
python install.py --check-only     # 检测环境；缺依赖会自动提示
python install.py --yes            # 全自动安装（依赖+ffmpeg+生成 config.yaml）
```

配置 LLM（转写不需要，成文才需要）：

```bash
# Windows PowerShell
$env:LLM_BASE_URL="https://api.deepseek.com/v1"; $env:LLM_API_KEY="sk-xxx"; $env:LLM_MODEL="deepseek-chat"
# 本地 Ollama（无需 key）
$env:LLM_BASE_URL="http://localhost:11434/v1"
```

## 常用命令

```bash
# ① 只转写（不调 LLM，零成本）——用户只想"提取字幕"时用这个
python -m v2a transcribe <视频或目录> -o output/字幕.md

# ② 一键成文（转写 + LLM 写公众号文章）
python -m v2a video <视频.mp4> --style tutorial

# ③ 已有字幕 → 文章
python -m v2a article output/字幕.md -o output/文章.md --style insight

# ④ 列出内置风格
python -m v2a styles
```

## 风格

内置 `styles/` 模板：`tutorial`（教程干货）/ `insight`（观点洞察）/ `story`（故事叙事）/ `custom`（自定义，编辑 `styles/custom.md`）。

## 约定

- 输出默认在 `output/`（已 gitignore）；
- 长视频自动 VAD 分段逐段转写，耗时段数增加，耐心等待；
- 成文失败先查 LLM key 是否配置（401 = key 为空或错误）；
- 不要自己重写脚本——直接调上面的 CLI。
