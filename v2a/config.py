# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a configuration loader.

Config sources (later wins):
  1. defaults
  2. config file (--config path.yaml)
  3. environment variables (LLM_BASE_URL / LLM_API_KEY / LLM_MODEL / V2A_STYLE)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

DEFAULTS = {
    "llm": {
        "provider": "openai_compatible",  # openai_compatible | ollama
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
        "temperature": 0.7,
        "max_tokens": 4096,
        "timeout": 120,
    },
    "asr": {
        "backend": "auto",  # auto | r2t2 | whisper
        "model_path": "",   # r2t2: HF repo id or local dir (empty = auto-detect ComfyUI models)
        "whisper_model": "small",
        "max_segment_seconds": 30.0,
        "vad_threshold_db": -40.0,
        "min_segment_seconds": 1.0,
    },
    "ffmpeg": "",
    "style": "tutorial",
    "output_dir": "output",
}


@dataclass
class Config:
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str = "") -> "Config":
        cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in DEFAULTS.items()}
        if config_path and os.path.isfile(config_path):
            with open(config_path, encoding="utf-8") as f:
                user_cfg = yaml.safe_load(f) or {}
            cfg = _deep_merge(cfg, user_cfg)

        # environment overrides
        env = os.environ
        if env.get("LLM_BASE_URL"):
            cfg["llm"]["base_url"] = env["LLM_BASE_URL"].strip()
        if env.get("LLM_API_KEY"):
            cfg["llm"]["api_key"] = env["LLM_API_KEY"].strip()
        if env.get("LLM_MODEL"):
            cfg["llm"]["model"] = env["LLM_MODEL"].strip()
        if env.get("V2A_STYLE"):
            cfg["style"] = env["V2A_STYLE"].strip()

        return cls(raw=cfg)

    def __getitem__(self, key):
        return self.raw[key]


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
