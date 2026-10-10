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

### 方式一：一键部署（推荐，自动装依赖 + ffmpeg + 生成配置）

**Windows**：双击 `setup.bat`（或命令行 `setup.bat`）
**Linux / macOS**：`./setup.sh`

脚本会：检测 Python ≥ 3.10 → 自动 `pip install` 依赖（librosa/qwen-asr 等）→ 找不到 ffmpeg 时自动下载便携版到项目内（无需管理员权限）→ 自动检测 R2T2 模型（ComfyUI models 或项目 models 目录）→ 无 GPU 自动切 CPU → 自动生成 `config.yaml`。

### 方式二：命令行手动安装

```bash
git clone https://github.com/dsAI-Q/video2article.git
cd video2article
python install.py --yes        # 全自动；--check-only 只看不装；--dry-run 演练
```

### 方式三：零安装（CLI 首次运行自动部署）

```bash
python -m v2a video 视频.mp4
```

首次运行 `transcribe` / `video` / `article` 时，若发现缺少 qwen-asr、ffmpeg 或模型，会自动启动 `install.py --yes` 补齐后继续执行；用 `--no-install` 可关闭自动安装。

配置 LLM（在线 API）后即可使用：

```bash
set LLM_BASE_URL=https://api.deepseek.com/v1
set LLM_API_KEY=sk-xxxx
set LLM_MODEL=deepseek-chat
# 或本地 Ollama: set LLM_BASE_URL=http://localhost:11434/v1

# ① 一键成文（缺依赖会自动安装）
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

### 方式 A：零配置（推荐，任何 agent 通用）

把仓库 clone 到本地后，**在仓库根目录启动你的 agent**（dsh / codex / trae / 豆包 CLI），agent 会自动读取根目录的 `AGENTS.md`，然后你直接用自然语言下指令即可：

> 把 `D:\视频\教程1.mp4` 转成公众号文章，教程风格
> 只提取这个目录下所有视频的字幕，不要调大模型

agent 会自己执行 `python -m v2a ...` 并把结果返回给你。

### 方式 B：注册成 dsh 全局 Skill（任何目录都能用）

仓库内 `dsh-skill/` 是 dsh 专用 skill 包（含 `meta.yaml` + `SKILL.md`），一行软链注册：

```powershell
# Windows（在 dsh 已安装的机器上）
mklink /J "%USERPROFILE%\.dsh\skills\video2article" "<仓库路径>\dsh-skill"
```

```bash
# Linux / macOS
ln -s "$(pwd)/dsh-skill" ~/.dsh/skills/video2article
```

之后在任何目录启动 dsh，都能直接说"用 v2a 把这个视频转成文章"，无需先 cd 进仓库。

### 豆包

仓库根目录 `SKILL.md` 是豆包 Skill 入口；也可在豆包内配合 `doubao-newmedia-writing` 做公众号成文的风格/格式精修。

## 排障

| 现象 | 处理 |
|---|---|
| `ffmpeg not found` | 安装 ffmpeg 并加入 PATH，或 config 指定 `ffmpeg:` 全路径 |
| `qwen-asr` 缺失 | `pip install qwen-asr==0.0.6`（会固定 transformers==4.57.6） |
| R2T2 模型找不到 | 下载模型并设置 `asr.model_path`；或改用 `backend: whisper` |
| LLM 请求失败 | 检查 `LLM_BASE_URL`/`LLM_API_KEY`；自动重试 3 次 |

## 许可

Apache-2.0。R2T2 上游封装（`v2a/backends/r2t2_asr.py`）版权归 NetEase Youdao，Apache-2.0。
