# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a — minimal LLM client (OpenAI-compatible chat completions).

Works with any OpenAI-compatible endpoint (DeepSeek / Doubao / Kimi / Zhipu /
SiliconFlow ...) and with local models via Ollama (http://localhost:11434/v1).

This is the ONLY network step of the pipeline and only runs when generating
the article from subtitles — everything else is local.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .utils import LOG


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self, cfg: dict, api_key: str = "", timeout: int | None = None):
        self.cfg = cfg
        self.api_key = (api_key or cfg.get("api_key", "") or "").strip()
        base = (cfg.get("base_url") or "").lower()
        is_local = "localhost" in base or "127.0.0.1" in base
        # local models need much longer (prefill + slow generation)
        self.timeout = timeout or int(cfg.get("timeout", 300 if is_local else 120))

    def _endpoint(self) -> str:
        base = (self.cfg.get("base_url") or "").strip().rstrip("/")
        if not base:
            raise LLMError("llm.base_url is not configured (see config.example.yaml)")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1") or base.endswith("/v1/"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def chat(self, messages: list, temperature: float | None = None,
             max_tokens: int | None = None) -> str:
        """Send a chat completion request and return the assistant text."""
        if not messages:
            raise LLMError("no messages to send")
        payload = {
            "model": self.cfg.get("model", ""),
            "messages": messages,
            "temperature": temperature if temperature is not None else self.cfg.get("temperature", 0.7),
            "max_tokens": max_tokens if max_tokens is not None else self.cfg.get("max_tokens", 4096),
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self._endpoint(), data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")

        last_err = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]
                return text
            except (urllib.error.HTTPError, urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
                last_err = e
                msg = str(getattr(e, "read", lambda: b"")())
                LOG.warning("LLM request failed (attempt %d): %s %s", attempt + 1, type(e).__name__, msg[:300])
                time.sleep(1.5 * (attempt + 1))
        raise LLMError(f"LLM request failed after 3 attempts: {last_err}")


def make_client(cfg: dict) -> LLMClient:
    return LLMClient(cfg.get("llm", {}))
