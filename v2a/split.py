# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — split a long utterance into segments (VAD + fixed-window fallback).

Local, free, no LLM involved. Segments are returned as
[(start_sec, end_sec, waveform_16k)].
"""

from __future__ import annotations

import numpy as np

FRAME_MS = 25
HOP_MS = 10


def _frame_energy(wav: np.ndarray, sr: int) -> np.ndarray:
    frame = int(sr * FRAME_MS / 1000)
    hop = int(sr * HOP_MS / 1000)
    n_frames = max(1, (wav.shape[0] - frame) // hop + 1)
    rms = np.zeros(n_frames)
    for i in range(n_frames):
        seg = wav[i * hop : i * hop + frame]
        rms[i] = float(np.sqrt(np.mean(seg ** 2))) if seg.size else 0.0
    eps = 1e-9
    return 20.0 * np.log10(rms + eps)


def _is_silence(rms_db: np.ndarray, threshold_db: float) -> np.ndarray:
    return rms_db < threshold_db


def split_audio(
    wav: np.ndarray,
    sr: int,
    max_segment_seconds: float = 30.0,
    vad_threshold_db: float = -40.0,
    min_segment_seconds: float = 1.0,
    merge_silence_seconds: float = 0.6,
) -> list:
    """Split wav into speech segments by silence detection.

    Non-silent spans are merged when the gap between them is short; spans
    longer than max_segment_seconds are hard-cut into fixed windows.
    Returns [(start_sec, end_sec, segment_wav)].
    """
    if wav.size == 0:
        return []
    dur = wav.shape[0] / float(sr)
    rms_db = _frame_energy(wav, sr)
    silence = _is_silence(rms_db, vad_threshold_db)

    hop = int(sr * HOP_MS / 1000)
    frame_sec = FRAME_MS / 1000.0

    # build speech spans from the silence mask
    spans = []
    in_speech = False
    start_idx = 0
    for i, s in enumerate(silence):
        if not in_speech and not s:
            in_speech = True
            start_idx = i
        elif in_speech and s:
            in_speech = False
            spans.append((start_idx, i))
    if in_speech:
        spans.append((start_idx, len(silence)))

    if not spans:
        # whole clip treated as one span
        spans = [(0, len(silence) - 1)]

    # merge spans with short gaps
    merged = []
    for a, b in spans:
        if merged and (a * frame_sec - merged[-1][1] * frame_sec) <= merge_silence_seconds:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))

    max_samples = int(max_segment_seconds * sr)
    min_samples = int(min_segment_seconds * sr)
    out = []
    for a, b in merged:
        seg_start = max(0, a * hop)
        seg_end = min(wav.shape[0], (b + 1) * hop)
        if seg_end - seg_start < min_samples:
            continue
        # hard-cut long spans
        while seg_end - seg_start > max_samples:
            cut = seg_start + max_samples
            out.append((seg_start / sr, cut / sr, wav[seg_start:cut]))
            seg_start = cut
        if seg_end - seg_start >= min_samples:
            out.append((seg_start / sr, seg_end / sr, wav[seg_start:seg_end]))

    if not out:  # fallback: whole file (respecting max window)
        for start in range(0, wav.shape[0], max_samples):
            end = min(wav.shape[0], start + max_samples)
            if end - start >= min_samples:
                out.append((start / sr, end / sr, wav[start:end]))
    return out
