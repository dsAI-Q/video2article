# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a.gpu — detect local GPU and recommend ASR settings accordingly."""

from __future__ import annotations

from .utils import LOG


def detect_gpu() -> dict:
    """Return {'available': bool, 'name': str, 'vram_gb': float, 'device': str}.

    Falls back to CPU gracefully if torch/CUDA not available.
    """
    try:
        import torch  # noqa: PLC0415
    except ImportError:
        return {"available": False, "name": "no torch", "vram_gb": 0.0, "device": "cpu"}

    if not torch.cuda.is_available():
        return {"available": False, "name": "CPU only", "vram_gb": 0.0, "device": "cpu"}

    try:
        name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
    except Exception:
        return {"available": True, "name": "unknown CUDA device", "vram_gb": 0.0, "device": "cuda:0"}

    return {"available": True, "name": name, "vram_gb": round(vram, 1), "device": "cuda:0"}


def recommend_settings(gpu: dict) -> dict:
    """Based on GPU info, return recommended ASR config.

    Returns dict with keys: device, max_segment_seconds, note.
    """
    if not gpu["available"]:
        return {
            "device": "cpu",
            "max_segment_seconds": 15.0,
            "note": "未检测到 GPU，使用 CPU 模式转写（较慢）。建议 LLM 使用在线 API（Deepseek 等）以节省时间。",
        }

    vram = gpu["vram_gb"]
    if vram >= 12:
        return {
            "device": "cuda:0",
            "max_segment_seconds": 30.0,
            "note": f"检测到 {gpu['name']}（{vram}GB 显存），GPU 加速模式。",
        }
    if vram >= 6:
        return {
            "device": "cuda:0",
            "max_segment_seconds": 20.0,
            "note": f"检测到 {gpu['name']}（{vram}GB 显存），GPU 加速（保守分段）。",
        }
    # small VRAM
    return {
        "device": "cuda:0",
        "max_segment_seconds": 12.0,
        "note": f"检测到 {gpu['name']}（{vram}GB 显存），显存较小，缩短分段避免 OOM。",
    }
