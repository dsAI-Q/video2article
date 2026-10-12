# coding=utf-8
# SPDX-License-Identifier: Apache-2.0
"""v2a.webui — local web UI for video-to-article.

Runs on http://127.0.0.1:8765 by default (avoids ComfyUI 7860, Ollama 11434,
common 8000/8080/3000). Configurable via `webui.port` in config.yaml.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

from .utils import LOG

try:
    from fastapi import FastAPI, BackgroundTasks
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    raise RuntimeError(
        "webui needs fastapi + uvicorn. Install with:\n"
        "  pip install fastapi uvicorn"
    )

WEB_DIR = Path(__file__).parent / "web"
TASKS: dict = {}  # task_id -> {status, log, result, error}


def create_app(config) -> FastAPI:
    app = FastAPI(title="v2a — video2article")

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/assets/{name}")
    def asset(name: str):
        safe = name.replace("..", "").replace("/", "")
        p = WEB_DIR / "assets" / safe
        if not p.is_file():
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(p)

    @app.get("/api/status")
    def status():
        from .gpu import detect_gpu, recommend_settings
        cfg = config.raw
        gpu = detect_gpu()
        rec = recommend_settings(gpu)
        # check R2T2 model
        r2t2_path = cfg.get("asr", {}).get("model_path", "")
        r2t2_ok = bool(r2t2_path) and os.path.isfile(os.path.join(r2t2_path, "config.json"))
        # ffmpeg
        ff = cfg.get("ffmpeg", "")
        ff_ok = bool(ff) and os.path.isfile(ff)
        # LLM configured? local models (localhost) don't need api_key
        llm = cfg.get("llm", {})
        has_key = bool(llm.get("api_key"))
        has_url = bool(llm.get("base_url"))
        has_model = bool(llm.get("model"))
        is_local = "localhost" in llm.get("base_url", "") or "127.0.0.1" in llm.get("base_url", "")
        llm_ok = bool(has_url and has_model and (has_key or is_local))
        return {
            "r2t2": {"ready": r2t2_ok, "path": r2t2_path},
            "ffmpeg": {"ready": ff_ok, "path": ff},
            "llm": {"configured": llm_ok, "model": llm.get("model", ""), "local": is_local},
            "gpu": gpu,
            "recommendation": rec,
            "output_dir": cfg.get("output_dir", "output"),
        }

    @app.get("/api/config")
    def get_config():
        cfg = config.raw
        # mask api key
        llm = dict(cfg.get("llm", {}))
        if llm.get("api_key"):
            llm["api_key"] = llm["api_key"][:6] + "****"
        return {"llm": llm, "asr": cfg.get("asr", {}), "style": cfg.get("style", "tutorial")}

    @app.post("/api/config")
    def save_config(new: dict):
        # only allow whitelisted keys
        llm = new.get("llm", {})
        if llm.get("api_key") and "****" not in llm.get("api_key", ""):
            config.raw["llm"]["api_key"] = llm["api_key"]
        if llm.get("base_url"):
            config.raw["llm"]["base_url"] = llm["base_url"]
        if llm.get("model"):
            config.raw["llm"]["model"] = llm["model"]
        if new.get("style"):
            config.raw["style"] = new["style"]
        # persist
        import yaml
        cfg_path = "config.yaml"
        with open(cfg_path, "w", encoding="utf-8") as f:
            yaml.dump(config.raw, f, allow_unicode=True, sort_keys=False)
        return {"ok": True}

    @app.post("/api/run")
    def run(payload: dict, background: BackgroundTasks):
        url = (payload.get("url") or "").strip()
        local_file = (payload.get("file") or "").strip()
        style = payload.get("style") or config.raw.get("style", "tutorial")
        if not url and not local_file:
            return JSONResponse({"error": "url or file is required"}, status_code=400)

        task_id = uuid.uuid4().hex[:8]
        TASKS[task_id] = {"status": "running", "log": [], "result": None, "error": None, "ts": time.time()}
        background.add_task(_run_task, task_id, url, local_file, style, config)
        return {"task_id": task_id}

    @app.get("/api/task/{task_id}")
    def task(task_id: str):
        t = TASKS.get(task_id)
        if not t:
            return JSONResponse({"error": "not found"}, status_code=404)
        return t

    @app.post("/api/cancel")
    def cancel():
        TASKS.clear()
        return {"ok": True}

    @app.post("/api/flush_gpu")
    def flush_gpu():
        """Release CUDA VRAM cache and run gc."""
        import gc
        result = {"alloc_before_mb": 0, "alloc_after_mb": 0, "reserved_before_mb": 0, "reserved_after_mb": 0}
        try:
            import torch
            if torch.cuda.is_available():
                result["alloc_before_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024)
                result["reserved_before_mb"] = round(torch.cuda.memory_reserved() / 1024 / 1024)
                # unload any cached R2T2 model first
                try:
                    from .asr import unload_r2t2
                    unload_r2t2()
                except Exception:
                    pass
                gc.collect()
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                result["alloc_after_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024)
                result["reserved_after_mb"] = round(torch.cuda.memory_reserved() / 1024 / 1024)
        except Exception as e:
            result["error"] = str(e)
        return result

    return app


def _run_task(task_id: str, url: str, local_file: str, style: str, config):
    t = TASKS[task_id]
    import logging

    class _TaskLogHandler(logging.Handler):
        def emit(self, record):
            try:
                t["log"].append(self.format(record))
            except Exception:
                pass

    handler = _TaskLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    v2a_logger = logging.getLogger("v2a")
    v2a_logger.addHandler(handler)
    v2a_logger.setLevel(logging.INFO)

    try:
        t["log"].append("启动 v2a 任务...")
        out_dir = os.path.abspath(config.raw.get("output_dir", "output"))
        os.makedirs(out_dir, exist_ok=True)

        if url:
            from .web import fetch_from_url, fetch_metadata, format_resources_section
            t["log"].append(f"抓取网页: {url}")
            info = fetch_from_url(url, out_dir, keep_video=False)
            if info.get("subtitle_path"):
                from .web import parse_subtitle_file, subtitle_markdown_from_web
                segs = parse_subtitle_file(info["subtitle_path"])
                md = subtitle_markdown_from_web(info["title"], url, segs)
                md_path = os.path.join(out_dir, f"{task_id}_字幕.md")
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write(md)
                t["log"].append(f"网页自带字幕，{len(segs)} 段")
            else:
                from .pipeline import run_transcribe
                md_path = run_transcribe(info["audio_path"], config, None)
            # metadata links
            resources = ""
            try:
                meta = fetch_metadata(url)
                resources = format_resources_section(meta["links"])
                t["log"].append(f"抓到 {len(meta['links'])} 个资源链接")
            except Exception as e:
                t["log"].append(f"资源链接抓取跳过: {e}")
        else:
            from .pipeline import run_transcribe
            md_path = run_transcribe(local_file, config, None)
            resources = ""

        t["log"].append("转写完成，开始生成文章...")
        with open(md_path, encoding="utf-8") as f:
            subtitle_text = f.read()
        from .article import generate_article
        # pass the real video title so LLM can correct ASR errors (e.g. Qwen vs k1me)
        video_title = info.get("title", "") if url else ""
        article = generate_article(
            subtitle_text,
            style=style,
            cfg_llm=config.raw.get("llm", {}),
            extra_context=f"视频真实标题：{video_title}" if video_title else "",
        )
        if resources:
            article = article.rstrip() + "\n" + resources

        art_path = os.path.join(out_dir, f"{task_id}_文章.md")
        with open(art_path, "w", encoding="utf-8") as f:
            f.write(article)

        # self-check
        from .check import check_article, format_report
        issues = check_article(article, web_mode=bool(url), video_title=info.get("title", "") if url else "")
        report = format_report(issues)

        t["result"] = {
            "article": article,
            "article_path": art_path,
            "subtitle_path": md_path,
            "check_report": report,
        }
        t["status"] = "done"
        t["log"].append("完成！")
    except Exception as e:
        t["status"] = "error"
        t["error"] = str(e)
        t["log"].append(f"错误: {e}")
    finally:
        # always free R2T2 VRAM after the task
        try:
            from .asr import unload_r2t2
            unload_r2t2()
            t["log"].append("已释放 R2T2 显存缓存。")
        except Exception:
            pass


def main(config):
    port = int(config.raw.get("webui", {}).get("port", 8765))
    host = config.raw.get("webui", {}).get("host", "127.0.0.1")
    app = create_app(config)
    LOG.info("v2a webui at http://%s:%d", host, port)
    # auto-open browser (cross-platform)
    def _open():
        import webbrowser
        webbrowser.open(f"http://{host}:{port}")
    threading.Timer(1.0, _open).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
