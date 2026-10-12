# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — ASR backends (all local, free, no LLM involved).

* r2t2    : Confucius4-R2T2 (NetEase Youdao / Qwen3-ASR arch), 2B, multilingual.
            Needs: qwen-asr + transformers==4.57.6 (see requirements.txt).
* whisper : faster-whisper (optional, pip install faster-whisper).
"""

from __future__ import annotations

import os

import numpy as np

from .utils import LOG

# module-level model cache: keep the loaded model alive across segments
_R2T2_MODEL = {"obj": None, "key": None}


def _detect_comfyui_r2t2_path() -> str | None:
    """Try to find an already-downloaded R2T2 checkpoint under ComfyUI models."""
    candidates = []
    for root in (
        os.environ.get("COMFYUI_MODELS_DIR", ""),
        r"ComfyUI\models",
        os.path.join(os.path.expanduser("~"), "ComfyUI", "models"),
    ):
        if root and os.path.isdir(root):
            p = os.path.join(root, "r2t2", "netease-youdao", "Confucius4-R2T2")
            if os.path.isfile(os.path.join(p, "config.json")):
                candidates.append(p)
    return candidates[0] if candidates else None


def _load_r2t2(model_path: str, device: str = "cuda:0") -> object:
    """Load R2T2ASRModel (vendored from upstream, Apache-2.0)."""
    key = (model_path, device)
    if _R2T2_MODEL["key"] == key and _R2T2_MODEL["obj"] is not None:
        return _R2T2_MODEL["obj"]
    try:
        from .backends.r2t2_asr import R2T2ASRModel
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "R2T2 backend needs `qwen-asr` (pip install -r requirements.txt). "
            f"Missing: {e.name}"
        ) from e

    import torch  # noqa: PLC0415
    LOG.info("loading R2T2 model from %s (device=%s, bfloat16)...", model_path, device)
    asr = R2T2ASRModel.from_pretrained(
        model_path,
        dtype=torch.bfloat16,
        device_map=device,
        max_new_tokens=512,
    )
    _R2T2_MODEL.update(key=key, obj=asr)
    return asr


def unload_r2t2() -> None:
    """Drop the cached R2T2 model and free VRAM/RAM. Call after transcription finishes."""
    obj = _R2T2_MODEL.get("obj")
    if obj is None:
        return
    try:
        del obj
    except Exception:
        pass
    _R2T2_MODEL.update(key=None, obj=None)
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            LOG.info("R2T2 unloaded, VRAM freed.")
    except Exception:
        pass


class R2T2Engine:
    name = "r2t2"

    def __init__(self, model_path: str = "", device: str = "auto"):
        import torch  # noqa: PLC0415
        if device in ("auto", "", "cuda"):
            self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        path = model_path.strip() or _detect_comfyui_r2t2_path()
        if not path:
            raise RuntimeError(
                "R2T2 model not found. Set `asr.model_path` in config to a local "
                "checkpoint directory or an HF repo id, or use backend='whisper'."
            )
        self.model_path = path

    def transcribe_segment(self, wav16k: np.ndarray) -> str:
        asr = _load_r2t2(self.model_path, self.device)
        results = asr.transcribe(
            audio=[(np.asarray(wav16k, dtype=np.float32), 16000)],
            language=[None],
            context="",
            return_time_stamps=False,
        )
        if not results:
            return ""
        return str(results[0].text)


class WhisperEngine:
    name = "whisper"

    def __init__(self, model_size: str = "small", device: str = "cuda:0"):
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError:
            raise RuntimeError(
                "whisper backend needs `faster-whisper` (pip install faster-whisper). "
                "Alternatively use backend='r2t2'."
            ) from None
        import torch  # noqa: PLC0415
        dev = "cuda" if (device and "cuda" in str(device) and torch.cuda.is_available()) else "cpu"
        self.model = WhisperModel(model_size, device=dev, compute_type="float16" if dev == "cuda" else "int8")

    def transcribe_segment(self, wav16k: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            (np.ascontiguousarray(wav16k, dtype=np.float32), 16000),
            language=None,
            vad_filter=True,
        )
        return "".join(seg.text for seg in segments).strip()


def get_engine(asr_cfg: dict) -> object:
    """Pick an engine: auto -> r2t2 if importable else whisper.

    If device is 'auto' or empty, auto-detect GPU and pick device + segment length.
    """
    from .gpu import detect_gpu, recommend_settings

    gpu = detect_gpu()
    rec = recommend_settings(gpu)
    device = (asr_cfg.get("device") or "auto").strip()
    if device in ("auto", "", "cuda" if gpu["available"] else "cpu"):
        device = rec["device"]
        LOG.info("GPU detect: %s", rec["note"])
        # auto-adjust segment length if user didn't override
        asr_cfg.setdefault("max_segment_seconds", rec["max_segment_seconds"])

    backend = (asr_cfg.get("backend") or "auto").strip().lower()
    if backend == "r2t2" or backend == "auto":
        try:
            import qwen_asr  # noqa: F401
            return R2T2Engine(
                model_path=asr_cfg.get("model_path", ""),
                device=device,
            )
        except (ModuleNotFoundError, RuntimeError) as e:
            if backend == "r2t2":
                raise
            LOG.info("R2T2 unavailable (%s), falling back to whisper.", str(e)[:80])
    return WhisperEngine(
        model_size=asr_cfg.get("whisper_model", "small"),
        device=device,
    )
