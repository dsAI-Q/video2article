# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — end-to-end pipeline (video -> subtitles -> article)."""

from __future__ import annotations

import os
import re

import numpy as np

from .asr import get_engine
from .config import Config
from .extract import extract_audio
from .split import split_audio
from .utils import LOG, ensure_dir, find_ffmpeg, fmt_ts


def _safe_name(path: str) -> str:
    base = os.path.splitext(os.path.basename(path))[0]
    return re.sub(r"[^\w\-_.\u4e00-\u9fff]+", "_", base).strip("_") or "input"


def _load_wav(path: str) -> tuple:
    import librosa  # noqa: PLC0415
    wav, sr = librosa.load(path, sr=16000, mono=True)
    return np.asarray(wav, dtype=np.float32), int(sr)


def subtitle_markdown(title: str, source: str, segments: list, backend: str, total_sec: float) -> str:
    lines = [
        f"# {title}",
        f"源文件: {source}",
        f"转写引擎: {backend}",
        f"总时长: {fmt_ts(total_sec)}",
        "",
    ]
    for start, end, text in segments:
        lines.append(f"## [{fmt_ts(start)} - {fmt_ts(end)}]")
        lines.append(text.strip())
        lines.append("")
    return "\n".join(lines)


def run_transcribe(
    input_path: str,
    config: Config,
    out_md: str = "",
) -> str:
    """Video(s) -> 16k wav -> VAD segments -> ASR -> timestamped markdown."""
    files = []
    if os.path.isdir(input_path):
        for ext in (".mp4", ".mkv", ".avi", ".mov", ".flv", ".wav", ".mp3", ".flac", ".m4a"):
            files.extend(sorted(
                os.path.join(input_path, f) for f in os.listdir(input_path)
                if f.lower().endswith(ext)
            ))
    else:
        files = [input_path]
    if not files:
        raise FileNotFoundError(f"no video/audio files found under {input_path}")

    ffmpeg = find_ffmpeg(config.raw.get("ffmpeg", ""))
    out_dir = os.path.abspath(ensure_dir(config.raw.get("output_dir", "output")))
    engine = get_engine(config.raw["asr"])
    LOG.info("ASR backend: %s", engine.name)

    all_docs = []
    for f in files:
        name = _safe_name(f)
        wav_path = os.path.join(out_dir, f"{name}_16k.wav")
        # Only a real wav can be copied as-is; every other format (mp4/mkv/m4a/mp3/flac/webm...)
        # must go through ffmpeg to become 16k mono pcm wav.
        if f.lower().endswith(".wav"):
            _copy_audio(f, wav_path)
        else:
            extract_audio(f, wav_path, ffmpeg)
        wav, sr = _load_wav(wav_path)
        total_sec = wav.shape[0] / float(sr)

        segs = split_audio(
            wav, sr,
            max_segment_seconds=float(config.raw["asr"].get("max_segment_seconds", 30)),
            vad_threshold_db=float(config.raw["asr"].get("vad_threshold_db", -40)),
            min_segment_seconds=float(config.raw["asr"].get("min_segment_seconds", 1)),
        )
        LOG.info("%s: %.1fs audio -> %d segments", name, total_sec, len(segs))

        results = []
        for i, (st, en, seg_wav) in enumerate(segs, 1):
            text = engine.transcribe_segment(seg_wav)
            results.append((st, en, text))
            LOG.info("  seg %d/%d [%s-%s] %s", i, len(segs), fmt_ts(st), fmt_ts(en), text[:60])

        doc = subtitle_markdown(name, os.path.basename(f), results, engine.name, total_sec)
        all_docs.append(doc)

    combined = "\n\n---\n\n".join(all_docs)
    out_path = out_md or os.path.join(out_dir, f"{_safe_name(files[0])}_字幕.md")
    ensure_dir(os.path.dirname(os.path.abspath(out_path)))
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(combined)
    LOG.info("subtitles saved -> %s", out_path)
    # Free R2T2 VRAM after transcription — LLM step doesn't need it.
    try:
        from .asr import unload_r2t2
        unload_r2t2()
    except Exception:
        pass
    return out_path


def _copy_audio(src: str, dst: str) -> None:
    import shutil
    shutil.copyfile(src, dst)


def run_video(input_path: str, config: Config, extra_context: str = "") -> str:
    """Full pipeline: video -> subtitles -> article (only this step uses LLM)."""
    from .article import generate_article

    md_path = run_transcribe(input_path, config)
    with open(md_path, encoding="utf-8") as f:
        subtitle_text = f.read()
    article = generate_article(
        subtitle_text,
        style=config.raw.get("style", "tutorial"),
        cfg_llm=config.raw.get("llm", {}),
        extra_context=extra_context,
    )
    out_path = os.path.join(os.path.abspath(ensure_dir(config.raw.get("output_dir", "output"))),
                            f"{os.path.splitext(os.path.basename(md_path))[0]}_文章.md")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(article)
    LOG.info("article saved -> %s", out_path)
    return out_path
