# v2a — 视频转公众号文章

把本地教学/分享视频**批量**转为公众号文章。三步流水线，**只有最后一步调用大模型**，其余全本地、免费：

```
视频/音频 ──ffmpeg──▶ 16kHz 单声道 wav ──本地 ASR──▶ 带时间戳字幕 ──LLM──▶ 公众号文章
  (本地)          (本地)                    (本地)            (仅此步联网)
```

## 特性

- **费用最小化**：提取、VAD 分段、转写全部本地完成；只有「字幕 → 文章」一步调用大模型
- **双 ASR 后端**：默认 R2T2（Confucius4-R2T2，2B 多语种，中文教学视频效果好）；可选 faster-whisper
- **LLM 灵活**：任何 OpenAI 兼容在线 API（DeepSeek / 豆包 / Kimi / 智谱…）或本地 Ollama
- **长视频友好**：静音检测 VAD 分段（≤30s）+ 时间戳字幕，几十分钟视频也能跑
- **多 Agent 可用**：CLI + AGENTS.md（codex/dsh/trea）+ SKILL.md（豆包）
- **Win10 / Win11 / Linux / macOS**：只需 Python 3.10+ 与 ffmpeg

## 快速开始

```bash
git clone https://github.com/dsAI-Q/video2article.git
cd video2article
pip install -r requirements.txt
pip install qwen-asr==0.0.6        # R2T2 后端
# 可选: pip install faster-whisper

# 配置 LLM（在线 API）
set LLM_BASE_URL=https://api.deepseek.com/v1
set LLM_API_KEY=sk-xxxx
set LLM_MODEL=deepseek-chat
# 或本地 Ollama: set LLM_BASE_URL=http://localhost:11434/v1

# ① 一键成文
python -m v2a video 视频.mp4 --style tutorial

# ② 只转写（不调 LLM，零成本）
python -m v2a transcribe ./视频目录 -o 字幕.md

# ③ 已有字幕 → 文章
python -m v2a article 字幕.md -o 文章.md --style insight
```

## 模型（不在仓库内）

仓库本体远小于 50MB，可通过链接直接安装。R2T2 模型约 3.8GB，两种方式获取：

- **自动检测**：若本机 ComfyUI 已有 `ComfyUI/models/r2t2/netease-youdao/Confucius4-R2T2`，无需配置
- **手动下载**（推荐海外/国内均可）：

```bash
# 海外直连
huggingface-cli download netease-youdao/Confucius4-R2T2 --local-dir D:\models\r2t2

# 国内镜像
HF_ENDPOINT=https://hf-mirror.com huggingface-cli download netease-youdao/Confucius4-R2T2 --local-dir D:\models\r2t2
```

然后在 `config.yaml` 设置 `asr.model_path: D:\models\r2t2`。

## 配置

复制 `config.example.yaml` → `config.yaml` 修改；或环境变量覆盖 `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` / `V2A_STYLE`。

### 公众号风格

内置 4 种写作风格（`styles/*.yaml`），控制标题规则、语气、结构与排版：

| 风格 | 适用 | 命令 |
|---|---|---|
| `tutorial`（默认） | 教程 / 知识分享 | `--style tutorial` |
| `insight` | 行业分析 / 观点输出 | `--style insight` |
| `story` | 人物故事 / 经历分享 | `--style story` |
| `custom` | 自定义规范（编辑 styles/custom.md） | `--style custom` |

## 输出示例

转写字幕（`output/*_字幕.md`）：

```markdown
# 大圣Ai-3.25
源文件: 大圣Ai-3.25.mp4
转写引擎: r2t2
总时长: 00:03:25

## [00:00:00 - 00:00:24]
大家好，今天给大家讲一下怎么用 ComfyUI 批量出图……
```

公众号文章（`output/*_文章.md`）：主标题 + 2 个备选标题 + 正文（markdown）。

## 在各 Agent 中使用

- **codex / dsh / trea**：仓库根目录的 `AGENTS.md` 已声明工具用法，把仓库加入项目即可让 Agent 直接调用
- **豆包**：仓库根目录 `SKILL.md` 是豆包 Skill 入口；也可在豆包内配合 `doubao-newmedia-writing` 做公众号成文的风格/格式精修

## 排障

| 现象 | 处理 |
|---|---|
| `ffmpeg not found` | 安装 ffmpeg 并加入 PATH，或 config 指定 `ffmpeg:` 全路径 |
| `qwen-asr` 缺失 | `pip install qwen-asr==0.0.6`（会固定 transformers==4.57.6） |
| R2T2 模型找不到 | 下载模型并设置 `asr.model_path`；或改用 `backend: whisper` |
| LLM 请求失败 | 检查 `LLM_BASE_URL`/`LLM_API_KEY`；自动重试 3 次 |

## 许可

Apache-2.0。R2T2 上游封装（`v2a/backends/r2t2_asr.py`）版权归 NetEase Youdao，Apache-2.0。
