# AGENTS.md — v2a 接入说明（给 codex / dsh / trea / 豆包 等 agent）

## 这是什么

`v2a` 是一个**本地优先**的视频转公众号文章 CLI 工具：

```
视频/音频 →(ffmpeg, 本地)→ 16k wav →(R2T2/Whisper, 本地)→ 带时间戳字幕 →(LLM, 仅此一步联网)→ 公众号文章
```

只有「字幕 → 文章」这一步调用大模型（在线 API 或本地 Ollama），其余全部本地完成，费用最低。

## 安装

一键部署（自动装依赖 + ffmpeg + 生成 config.yaml）：

```bash
git clone https://github.com/dsAI-Q/video2article.git
cd video2article
python install.py --yes      # 全自动；--check-only 只检测；--dry-run 演练
```

或手动：

```bash
pip install -r requirements.txt        # 核心依赖（librosa/soundfile/pyyaml/numpy）
pip install qwen-asr==0.0.6            # R2T2 后端（会固定 transformers==4.57.6）
# 可选：pip install faster-whisper      # Whisper 后端
```

> 提示：`python -m v2a` 首次运行会自动检测环境，缺少 qwen-asr / ffmpeg / 模型时自动执行 install.py 补齐（`--no-install` 关闭）。

R2T2 模型（约 3.8GB）：
- 自动检测：若机器装有 ComfyUI 且模型在 `ComfyUI/models/r2t2/netease-youdao/Confucius4-R2T2`，无需配置；
- 手动下载：`huggingface-cli download netease-youdao/Confucius4-R2T2 --local-dir <你的目录>`，然后在 `config.yaml` 的 `asr.model_path` 指向该目录。

## 配置

复制 `config.example.yaml` 为 `config.yaml`，或直接用环境变量：

```bash
export LLM_BASE_URL=https://api.deepseek.com/v1
export LLM_API_KEY=sk-xxx
export LLM_MODEL=deepseek-chat
export V2A_STYLE=tutorial     # tutorial | insight | story | custom
```

本地模型（Ollama）：`LLM_BASE_URL=http://localhost:11434/v1`，无需 API key。

## 常用命令

```bash
# ① 只转写（免费、本地、不调 LLM）
python -m v2a transcribe 视频目录/或单个文件.mp4 -o 字幕.md

# ② 一键成文（转写 + LLM 写公众号文章，仅此步联网）
python -m v2a video 视频.mp4 --style tutorial --context "视频标题：xxx；目标读者：职场新人"

# ③ 已有字幕 → 文章
python -m v2a article 字幕.md -o 文章.md --style insight

# ④ 查看可用风格
python -m v2a styles

# ⑤ 从网页视频抓（B 站/YouTube/抖音等 1000+ 站点）
#    默认只抓字幕或音频（转文章最低需求），不要主动加 --keep-video
#    仅当用户明确说"下载/保存视频文件"时，才加 --keep-video 下完整 mp4
python -m v2a web "https://www.bilibili.com/video/BVxxxx" --no-article
```

## 在豆包等平台内使用

豆包 agent 可直接调用本 CLI（命令行执行），或把本仓库作为一个 Skill 使用（见 `SKILL.md`）。豆包内的公众号写作规范可用 `V2A_STYLE` 选择风格模板；如需更定制化的风格，编辑 `styles/*.yaml` 或参考 `styles/custom.md` 自定义提示词。

## 约定

- 输出默认在 `output/`（可在配置中改）；
- 转写输出为 Markdown 时间轴字幕（`## [mm:ss - mm:ss]`），可直接用 `v2a article` 消费；
- LLM 失败自动重试 3 次；断网时 `v2a transcribe` 依然可用（纯本地）。
