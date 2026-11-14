"""One native Hindsight daemon for all project banks in this installation."""
from __future__ import annotations

import os
import hashlib
import json
import threading
from pathlib import Path

from text2music.agent.hindsight_store import HindsightStore

_lock = threading.Lock()
_url = None
_started_here = False


def project_store(project_id: str) -> HindsightStore:
    global _url, _started_here
    with _lock:
        from hindsight_embed import get_embed_manager
        manager = get_embed_manager()
        if _url is not None and not manager.is_running("triceratops"):
            _url = None
        if _url is None:
            provider = os.environ.get("TRICERATOPS_MEMORY_PROVIDER", "auto")
            if provider == "auto":
                chat_provider = os.environ.get("TRICERATOPS_LLM_PROVIDER", "")
                provider = ("local" if chat_provider in {"ollama", "llama_cpp"}
                            else "remote" if chat_provider == "remote"
                            else "remote" if os.environ.get("QWEN_API_KEY") else "local")
            if provider not in {"remote", "local"}:
                raise ValueError("Memory provider must be remote or local")
            if provider == "remote":
                key = os.environ.get("QWEN_API_KEY", "")
                if not key:
                    raise RuntimeError("Project memory needs the configured API key")
                base_url = os.environ.get("QWEN_BASE_URL", "")
                model = os.environ.get("QWEN_MODEL", "")
            else:
                import sys
                from text2music.agent.llm_backend import ChatSettings, residency
                settings = ChatSettings.load("local")
                residency(settings)
                base_url = (settings.base_url.rstrip("/") + "/v1"
                            if sys.platform == "darwin" else settings.base_url)
                model = settings.model
                key = "local-only"
            if not base_url or not model:
                raise RuntimeError("Project memory needs a configured chat model and endpoint")
            embed_path = Path(os.environ.get("TRICERATOPS_HINDSIGHT_EMBED_PATH", ""))
            if not embed_path.is_dir() or not (embed_path / "model.safetensors").is_file():
                raise RuntimeError("Project memory model is missing. Open Settings and run Download & set up.")
            config = {
                "HINDSIGHT_API_LLM_PROVIDER": "openai",
                "HINDSIGHT_API_LLM_API_KEY": key,
                "HINDSIGHT_API_LLM_BASE_URL": base_url,
                "HINDSIGHT_API_LLM_MODEL": model,
                "HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS": "1024" if provider == "local" else "8192",
                "HINDSIGHT_API_RETAIN_CHUNK_SIZE": "384" if provider == "local" else "3000",
                "HINDSIGHT_API_EMBEDDINGS_PROVIDER": "local",
                "HINDSIGHT_API_EMBEDDINGS_LOCAL_MODEL": str(embed_path),
                "HINDSIGHT_API_RERANKER_PROVIDER": "flashrank",
                "HINDSIGHT_API_MCP_ENABLED": "false",
            }
            if provider == "local":
                config["HINDSIGHT_API_LLM_EXTRA_BODY"] = '{"chat_template_kwargs":{"enable_thinking":false}}'
            fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()
            runs_dir = os.environ.get("TRICERATOPS_RUNS_DIR", "")
            stamp = Path(runs_dir).parent / "hindsight-profile.sha256" if runs_dir else None
            existing_stamp = stamp.read_text(encoding="ascii").strip() if stamp and stamp.is_file() else ""
            # Settings may have changed the provider or key while the old
            # daemon stayed alive. Reuse it only for the exact same config.
            if not _started_here and manager.is_running("triceratops") and existing_stamp != fingerprint:
                try:
                    stopped = manager.stop("triceratops")
                except SystemError:
                    stopped = not manager.is_running("triceratops")
                if not stopped or manager.is_running("triceratops"):
                    raise RuntimeError("The previous project memory service could not stop")
            if not manager.ensure_running(config, "triceratops"):
                raise RuntimeError("Hindsight project memory could not start")
            if os.name != "nt":
                profile = Path.home() / ".hindsight" / "profiles" / "triceratops.env"
                if not profile.is_file():
                    raise RuntimeError("Hindsight project memory profile was not created")
                profile.chmod(0o600)
            _url = manager.get_url("triceratops")
            if stamp:
                stamp.parent.mkdir(parents=True, exist_ok=True)
                temporary = stamp.with_suffix(".tmp")
                temporary.write_text(fingerprint, encoding="ascii")
                temporary.replace(stamp)
            _started_here = True
        return HindsightStore(_url, "triceratops-" + project_id)


def verify_memory() -> None:
    store = project_store("setup-check")
    document_id = "triceratops-fact-setup-check"
    sample = "The project prefers a sparse piano at 91 BPM."
    store.retain(document_id, sample, "constraint")
    try:
        if not store.recall("What instrument and tempo does this project prefer?"):
            raise RuntimeError("Project memory did not return the saved requirement")
    finally:
        store.delete(document_id)
    if store.documents():
        raise RuntimeError("Project memory did not clear its setup check")
