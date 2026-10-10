---
name: video2article
description: 视频转公众号文章工具（v2a）。把本地教学/分享视频批量转为带时间戳字幕，再用大模型生成公众号文章；仅成文一步调用 LLM（支持在线 API 或本地 Ollama），提取/转写全本地免费。当用户要求「视频转文字/转公众号文章/视频批量生成文章/提取视频字幕」时使用。
---

# v2a — 视频转公众号文章

## 流程（费用最小化）

1. **提取**：ffmpeg 提取音轨 → 16kHz 单声道 wav（本地）
2. **转写**：R2T2（默认）或 Whisper 本地 ASR，VAD 静音分段后逐段转写 → 带时间戳 Markdown 字幕（本地）
3. **成文**：仅此步调用 LLM（DeepSeek/豆包等 OpenAI 兼容 API，或本地 Ollama）→ 公众号文章

## 安装（自动）

```bash
python install.py --yes        # 全自动：依赖 + ffmpeg + config.yaml
python -m v2a transcribe <视频或目录>   # 首次运行若缺依赖会自动补齐
```

或双击 `setup.bat`（Windows）/ `./setup.sh`（Linux/macOS）。

## 使用

```bash
# 转写（不调 LLM）
python -m v2a transcribe <视频或目录> -o 字幕.md

# 一键成文
python -m v2a video <视频> --style tutorial

# 字幕 → 文章
python -m v2a article <字幕.md> -o 文章.md

# 从网页视频抓字幕/音频（B 站/YouTube/抖音等）
# 默认只抓字幕或音频（转文章最低需求），不下载完整视频
python -m v2a web <网页URL> --no-article
# 仅当用户明确说"下载/保存视频文件"时，才加 --keep-video 下载完整 mp4
python -m v2a web <网页URL> --keep-video

python -m v2a styles   # 列出风格
```

## 配置

环境变量：`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `V2A_STYLE`，或复制 `config.example.yaml` 为 `config.yaml` 修改。

- 在线 API：`LLM_BASE_URL=https://api.deepseek.com/v1` + key + model
- 本地 Ollama：`LLM_BASE_URL=http://localhost:11434/v1`（无需 key）

## 风格（公众号写作）

内置 `styles/` 模板（tutorial / insight / story / custom），可在 config 或 `--style` 指定；自定义请编辑 `styles/*.yaml`（标题规则、语气、结构、排版要求）。

## 说明

- 仓库不含模型（<50MB），R2T2 模型约 3.8GB 由用户自行下载到本地目录（或自动检测 ComfyUI 已有模型）。
- 转写输出 Markdown 时间轴字幕；成文输出 markdown 文章（标题 + 备选标题 + 正文）。
